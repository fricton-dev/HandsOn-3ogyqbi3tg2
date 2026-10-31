"""共有モード: DynamoDB 実装 (研修生全員で 1 テーブルを共有する)。

テーブル設計 (pk: 文字列 / sk: 文字列 の 1 テーブル):
  ユーザー          pk=USER#<username>   sk=PROFILE            display_name, password_hash, avatar_color, status_message
  ユーザー一覧      pk=USERS             sk=USER#<username>    display_name, avatar_color, status_message   (検索用のディレクトリ)
  セッション        pk=SESSION#<token>   sk=SESSION            user_id, expires_at(TTL)
  ルーム            pk=ROOM#<roomId>     sk=META               type, name, created_by, created_at
  ルームのメンバー  pk=ROOM#<roomId>     sk=MEMBER#<username>  last_read_message_id
  メッセージ        pk=ROOM#<roomId>     sk=MSG#<ULID>         sender_id, sender_name, sender_color, type, content, deleted, created_at
  参加ルーム        pk=USER#<username>   sk=ROOM#<roomId>      (リンクのみ)

メッセージは「ルームごとに時系列順」が最頻のアクセスなので、ルームをパーティションキーにしている。
ユーザー ID は username をそのまま使う (全 EC2 で同じアカウントになる)。
"""
import secrets
import time
from datetime import datetime, timezone

import boto3
from boto3.dynamodb.conditions import Attr, Key
from botocore.config import Config
from botocore.exceptions import ClientError

from .ids import ulid
from .storage_base import ConflictError, NotFoundError

SESSION_DAYS = 30


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DynamoStorage:
    name = "dynamodb"

    def __init__(self, table: str, region: str, access_key_id: str = "", secret_access_key: str = "",
                 endpoint_url: str = ""):
        kwargs = {"region_name": region or "ap-northeast-1"}
        if access_key_id and secret_access_key:
            kwargs.update(aws_access_key_id=access_key_id, aws_secret_access_key=secret_access_key)
        session = boto3.session.Session(**kwargs)
        cfg = Config(connect_timeout=3, read_timeout=8, retries={"max_attempts": 2})
        self.resource = session.resource("dynamodb", endpoint_url=endpoint_url or None, config=cfg)
        self.client = self.resource.meta.client
        self.table_name = table
        self.table = self.resource.Table(table)
        self.region = kwargs["region_name"]
        self.credential_source = "設定画面のアクセスキー" if access_key_id else "IAM ロール / 環境変数"

    # ---- 稼働確認 ----
    def ping(self) -> dict:
        try:
            desc = self.client.describe_table(TableName=self.table_name)["Table"]
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code == "ResourceNotFoundException":
                raise RuntimeError(f"テーブル '{self.table_name}' がリージョン {self.region} に見つかりません")
            if code in ("AccessDeniedException", "UnrecognizedClientException", "InvalidSignatureException"):
                raise RuntimeError(f"権限または認証情報の問題です ({code})。EC2 の IAM ロールに DynamoDB の権限があるか確認してください")
            raise RuntimeError(f"DynamoDB エラー: {code or e}")
        except Exception as e:  # noqa: BLE001
            msg = str(e)
            if "Unable to locate credentials" in msg:
                raise RuntimeError("AWS の認証情報がありません。EC2 に IAM ロールを付けるか、アクセスキーを入力してください")
            raise RuntimeError(f"接続に失敗しました: {msg[:200]}")
        keys = {k["AttributeName"]: k["KeyType"] for k in desc.get("KeySchema", [])}
        if keys.get("pk") != "HASH" or keys.get("sk") != "RANGE":
            raise RuntimeError(f"キー構成が違います (必要: pk=HASH, sk=RANGE / 実際: {keys})")
        return {"ok": True, "detail": f"テーブル '{self.table_name}' ({self.region}) に接続できました。"
                                      f"状態: {desc.get('TableStatus')}, 項目数(概算): {desc.get('ItemCount', 0)}"}

    def info(self) -> dict:
        return {"backend": "dynamodb", "table": self.table_name, "region": self.region}

    # ---- 内部ヘルパ ----
    def _get(self, pk, sk):
        return self.table.get_item(Key={"pk": pk, "sk": sk}).get("Item")

    def _query_all(self, **kwargs):
        items = []
        while True:
            res = self.table.query(**kwargs)
            items.extend(res.get("Items", []))
            if "LastEvaluatedKey" not in res:
                return items
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]

    @staticmethod
    def _user_from_item(it) -> dict:
        return {
            "id": it["username"], "username": it["username"], "display_name": it["display_name"],
            "avatar_color": it["avatar_color"], "status_message": it.get("status_message", ""),
        }

    @staticmethod
    def _msg_from_item(it) -> dict:
        deleted = bool(it.get("deleted"))
        return {
            "id": it["sk"][4:], "room_id": it["pk"][5:],
            "sender": {"id": it["sender_id"], "display_name": it["sender_name"], "avatar_color": it["sender_color"]},
            "type": it["type"], "content": "" if deleted else it.get("content", ""),
            "deleted": deleted, "created_at": it["created_at"],
        }

    # ---- ユーザー ----
    def create_user(self, username, display_name, password_hash, avatar_color):
        item = {"pk": f"USER#{username}", "sk": "PROFILE", "username": username, "display_name": display_name,
                "password_hash": password_hash, "avatar_color": avatar_color, "status_message": "",
                "created_at": _now_iso()}
        try:
            self.table.put_item(Item=item, ConditionExpression="attribute_not_exists(pk)")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                raise ConflictError("そのユーザー名は既に使われています")
            raise
        self.table.put_item(Item={"pk": "USERS", "sk": f"USER#{username}", "username": username,
                                  "display_name": display_name, "avatar_color": avatar_color, "status_message": ""})
        return self._user_from_item(item)

    def get_user_with_hash(self, username):
        it = self._get(f"USER#{username}", "PROFILE")
        if not it:
            return None
        u = self._user_from_item(it)
        u["password_hash"] = it["password_hash"]
        return u

    def get_user(self, user_id):
        it = self._get(f"USER#{user_id}", "PROFILE")
        return self._user_from_item(it) if it else None

    def update_user(self, user_id, display_name, status_message):
        sets, names, values = [], {}, {}
        if display_name is not None:
            sets.append("#dn = :dn"); names["#dn"] = "display_name"; values[":dn"] = display_name
        if status_message is not None:
            sets.append("#sm = :sm"); names["#sm"] = "status_message"; values[":sm"] = status_message
        if sets:
            for key in ({"pk": f"USER#{user_id}", "sk": "PROFILE"}, {"pk": "USERS", "sk": f"USER#{user_id}"}):
                self.table.update_item(Key=key, UpdateExpression="SET " + ", ".join(sets),
                                       ExpressionAttributeNames=names, ExpressionAttributeValues=values)
        return self.get_user(user_id)

    def search_users(self, q, exclude_id):
        items = self._query_all(KeyConditionExpression=Key("pk").eq("USERS") & Key("sk").begins_with("USER#"))
        ql = (q or "").lower()
        out = [self._user_from_item(it) for it in items
               if it["username"] != exclude_id and (ql in it["display_name"].lower() or ql in it["username"].lower())]
        out.sort(key=lambda u: u["display_name"])
        return out[:100]

    # ---- セッション ----
    def create_session(self, user_id):
        token = secrets.token_urlsafe(32)
        self.table.put_item(Item={"pk": f"SESSION#{token}", "sk": "SESSION", "user_id": user_id,
                                  "expires_at": int(time.time()) + SESSION_DAYS * 86400})
        return token

    def delete_session(self, token):
        self.table.delete_item(Key={"pk": f"SESSION#{token}", "sk": "SESSION"})

    def user_from_token(self, token):
        if not token:
            return None
        it = self._get(f"SESSION#{token}", "SESSION")
        if not it or int(it.get("expires_at", 0)) < time.time():
            return None
        return self.get_user(it["user_id"])

    # ---- ルーム ----
    def _members(self, room_id) -> list[dict]:
        items = self._query_all(KeyConditionExpression=Key("pk").eq(f"ROOM#{room_id}") & Key("sk").begins_with("MEMBER#"))
        if not items:
            return []
        keys = [{"pk": f"USER#{it['sk'][7:]}", "sk": "PROFILE"} for it in items]
        profiles = {}
        for i in range(0, len(keys), 100):
            res = self.resource.batch_get_item(RequestItems={self.table_name: {"Keys": keys[i:i + 100]}})
            for p in res.get("Responses", {}).get(self.table_name, []):
                profiles[p["username"]] = p
        out = []
        for it in items:
            uid = it["sk"][7:]
            p = profiles.get(uid, {})
            out.append({"id": uid, "display_name": p.get("display_name", uid), "avatar_color": p.get("avatar_color", "#999999"),
                        "last_read_message_id": it.get("last_read_message_id", "")})
        out.sort(key=lambda m: m["id"])
        return out

    def is_member(self, room_id, user_id):
        return self._get(f"ROOM#{room_id}", f"MEMBER#{user_id}") is not None

    def room_member_ids(self, room_id):
        items = self._query_all(KeyConditionExpression=Key("pk").eq(f"ROOM#{room_id}") & Key("sk").begins_with("MEMBER#"),
                                ProjectionExpression="sk")
        return [it["sk"][7:] for it in items]

    def room_summary(self, room_id, me_id):
        meta = self._get(f"ROOM#{room_id}", "META")
        if not meta:
            return None
        members = self._members(room_id)
        me = next((m for m in members if m["id"] == me_id), None)
        my_last_read = me["last_read_message_id"] if me else ""

        last_items = self.table.query(KeyConditionExpression=Key("pk").eq(f"ROOM#{room_id}") & Key("sk").begins_with("MSG#"),
                                      ScanIndexForward=False, Limit=1).get("Items", [])
        last = self._msg_from_item(last_items[0]) if last_items else None

        unread = 0
        kwargs = dict(KeyConditionExpression=Key("pk").eq(f"ROOM#{room_id}") & Key("sk").gt(f"MSG#{my_last_read}"),
                      FilterExpression=Attr("sender_id").ne(me_id) & Attr("deleted").ne(True), Select="COUNT")
        while True:
            res = self.table.query(**kwargs)
            unread += res.get("Count", 0)
            if "LastEvaluatedKey" not in res:
                break
            kwargs["ExclusiveStartKey"] = res["LastEvaluatedKey"]

        if meta["type"] == "direct":
            other = next((m for m in members if m["id"] != me_id), None) or (members[0] if members else None)
            name = other["display_name"] if other else "（相手なし）"
            color = other["avatar_color"] if other else "#999999"
            partner_id = other["id"] if other else None
        else:
            name, color, partner_id = meta.get("name") or "グループ", "#5b8def", None

        return {
            "id": room_id, "type": meta["type"], "name": name, "avatar_color": color, "partner_id": partner_id,
            "members": members, "my_last_read_message_id": my_last_read, "unread_count": unread,
            "last_message": last,
            "last_activity_at": last["created_at"] if last else meta.get("created_at"),
            "created_at": meta.get("created_at"),
        }

    def list_rooms(self, me_id):
        links = self._query_all(KeyConditionExpression=Key("pk").eq(f"USER#{me_id}") & Key("sk").begins_with("ROOM#"),
                                ProjectionExpression="sk")
        rooms = [self.room_summary(it["sk"][5:], me_id) for it in links]
        rooms = [r for r in rooms if r]
        rooms.sort(key=lambda r: r["last_activity_at"] or "", reverse=True)
        return rooms

    def create_room(self, room_type, name, member_ids, creator):
        member_ids = sorted({str(m) for m in member_ids} | {creator["id"]})
        for uid in member_ids:
            if not self.get_user(uid):
                raise NotFoundError("存在しないユーザーが含まれています")
        if room_type == "direct":
            room_id = "dm_" + "_".join(member_ids)   # 同じ 2 人なら必ず同じ ID → 重複しない
        else:
            room_id = "g_" + ulid()
        meta = {"pk": f"ROOM#{room_id}", "sk": "META", "type": room_type, "name": name,
                "created_by": creator["id"], "created_at": _now_iso()}
        try:
            self.table.put_item(Item=meta, ConditionExpression="attribute_not_exists(pk)")
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                return room_id  # 既存の 1:1 ルーム
            raise
        with self.table.batch_writer() as bw:
            for uid in member_ids:
                bw.put_item(Item={"pk": f"ROOM#{room_id}", "sk": f"MEMBER#{uid}", "last_read_message_id": "",
                                  "joined_at": _now_iso()})
                bw.put_item(Item={"pk": f"USER#{uid}", "sk": f"ROOM#{room_id}", "joined_at": _now_iso()})
        if room_type == "group":
            self.insert_message(room_id, creator, "system", f"{creator['display_name']}がグループを作成しました")
        return room_id

    # ---- メッセージ ----
    def list_messages(self, room_id, before, after, limit):
        cond = Key("pk").eq(f"ROOM#{room_id}")
        if after:
            res = self.table.query(KeyConditionExpression=cond & Key("sk").gt(f"MSG#{after}"), Limit=limit)
            items = res.get("Items", [])
            return [self._msg_from_item(i) for i in items], len(items) == limit
        if before:
            cond = cond & Key("sk").between("MSG#", f"MSG#{before}")
            res = self.table.query(KeyConditionExpression=cond, ScanIndexForward=False, Limit=limit + 1)
            items = [i for i in res.get("Items", []) if i["sk"] != f"MSG#{before}"][:limit]
        else:
            cond = cond & Key("sk").begins_with("MSG#")
            items = self.table.query(KeyConditionExpression=cond, ScanIndexForward=False, Limit=limit).get("Items", [])
        items.reverse()
        return [self._msg_from_item(i) for i in items], len(items) == limit

    def _advance_read(self, room_id, user_id, message_id):
        try:
            self.table.update_item(
                Key={"pk": f"ROOM#{room_id}", "sk": f"MEMBER#{user_id}"},
                UpdateExpression="SET last_read_message_id = :id",
                ConditionExpression="attribute_exists(pk) AND (attribute_not_exists(last_read_message_id) OR last_read_message_id < :id)",
                ExpressionAttributeValues={":id": message_id},
            )
        except ClientError as e:
            if e.response["Error"]["Code"] != "ConditionalCheckFailedException":
                raise

    def insert_message(self, room_id, sender, mtype, content):
        mid = ulid()
        item = {"pk": f"ROOM#{room_id}", "sk": f"MSG#{mid}", "sender_id": sender["id"],
                "sender_name": sender["display_name"], "sender_color": sender["avatar_color"],
                "type": mtype, "content": content, "deleted": False, "created_at": _now_iso()}
        self.table.put_item(Item=item)
        self._advance_read(room_id, sender["id"], mid)
        return self._msg_from_item(item)

    def get_message(self, room_id, message_id):
        it = self._get(f"ROOM#{room_id}", f"MSG#{message_id}")
        return self._msg_from_item(it) if it else None

    def mark_read(self, room_id, user_id, message_id):
        self._advance_read(room_id, user_id, message_id)
        it = self._get(f"ROOM#{room_id}", f"MEMBER#{user_id}")
        return it.get("last_read_message_id", "") if it else None

    def unsend_message(self, room_id, message_id, user_id):
        it = self._get(f"ROOM#{room_id}", f"MSG#{message_id}")
        if not it or it["sender_id"] != user_id:
            return None
        if not it.get("deleted"):
            self.table.update_item(Key={"pk": f"ROOM#{room_id}", "sk": f"MSG#{message_id}"},
                                   UpdateExpression="SET deleted = :t", ExpressionAttributeValues={":t": True})
            it["deleted"] = True
        return self._msg_from_item(it)

    # ---- 初期データ ----
    def seed_demo(self):
        """共有テーブルにはデモデータを入れない (研修生が自分で登録する)"""
        return None
