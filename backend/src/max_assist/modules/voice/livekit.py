from collections.abc import Awaitable
from datetime import datetime, timedelta

from livekit import api

from max_assist.config import settings
from max_assist.utils import now


def room_token(room: str, identity: str, name: str) -> tuple[str, datetime]:
    ttl = timedelta(seconds=settings.voice_token_ttl_seconds)
    token = (
        api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
        .with_identity(identity)
        .with_name(name)
        .with_ttl(ttl)
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room,
                can_publish=True,
                can_publish_sources=["microphone"],
                can_subscribe=True,
                can_publish_data=False,
            )
        )
    )
    return token.to_jwt(), now() + ttl


async def skip_missing(call: Awaitable[object]) -> None:
    # в голос могли так и не зайти — тогда ни комнаты, ни участника нет, и это не ошибка
    try:
        await call
    except api.TwirpError as error:
        if error.code != api.TwirpErrorCode.NOT_FOUND:
            raise


class Rooms:
    def client(self) -> api.LiveKitAPI:
        return api.LiveKitAPI(settings.livekit_api_url, settings.livekit_api_key, settings.livekit_api_secret)

    async def open(self, room: str) -> None:
        recording = api.RoomCompositeEgressRequest(
            audio_only=True,
            # для голоса хватает 32 кбит/с: около 15 МБ на час разговора
            advanced=api.EncodingOptions(audio_codec=api.AudioCodec.OPUS, audio_bitrate=32),
            file_outputs=[
                api.EncodedFileOutput(
                    file_type=api.EncodedFileType.OGG,
                    filepath=f"/out/{room}.ogg",
                    disable_manifest=True,
                )
            ],
        )
        async with self.client() as client:
            # запись стартует сама, когда в комнату войдёт первый человек
            await client.room.create_room(
                api.CreateRoomRequest(
                    name=room,
                    empty_timeout=300,
                    max_participants=4,
                    egress=api.RoomEgress(room=recording),
                )
            )

    async def remove(self, room: str, identity: str) -> None:
        async with self.client() as client:
            await skip_missing(
                client.room.remove_participant(api.RoomParticipantIdentity(room=room, identity=identity))
            )

    async def close(self, room: str) -> None:
        async with self.client() as client:
            await skip_missing(client.room.delete_room(api.DeleteRoomRequest(room=room)))

    async def ping(self) -> bool:
        try:
            async with self.client() as client:
                await client.room.list_rooms(api.ListRoomsRequest())
        except Exception:
            return False
        return True


rooms = Rooms()
