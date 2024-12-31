from __future__ import annotations

import json
from dataclasses import dataclass

from openhands.core.config.app_config import AppConfig
from openhands.core.logger import openhands_logger as logger
from openhands.server.data_models.conversation_metadata_result_set import ConversationMetadataResultSet
from openhands.storage import get_file_store
from openhands.storage.conversation.conversation_store import ConversationStore
from openhands.server.data_models.conversation_metadata import ConversationMetadata
from openhands.storage.files import FileStore
from openhands.storage.locations import CONVERSATION_BASE_DIR, get_conversation_metadata_filename
from openhands.utils.async_utils import call_sync_from_async
from openhands.utils.search_utils import offset_to_page_id, page_id_to_offset


@dataclass
class FileConversationStore(ConversationStore):
    file_store: FileStore

    async def save_metadata(self, metadata: ConversationMetadata):
        json_str = json.dumps(metadata.__dict__)
        path = self.get_conversation_metadata_filename(metadata.conversation_id)
        await call_sync_from_async(self.file_store.write, path, json_str)

    async def get_metadata(self, conversation_id: str) -> ConversationMetadata:
        path = self.get_conversation_metadata_filename(conversation_id)
        json_str = await call_sync_from_async(self.file_store.read, path)
        return ConversationMetadata(**json.loads(json_str))

    async def delete_metadata(self, conversation_id: str) -> None:
        path = self.get_conversation_metadata_filename(conversation_id)
        await call_sync_from_async(self.file_store.delete, path)

    async def exists(self, conversation_id: str) -> bool:
        path = self.get_conversation_metadata_filename(conversation_id)
        try:
            await call_sync_from_async(self.file_store.read, path)
            return True
        except FileNotFoundError:
            return False
        
    async def search(
        self, 
        page_id: str | None = None,
        limit: int = 20,
    ) -> ConversationMetadataResultSet:
        conversations = []
        metadata_dir = self.get_conversation_metadata_dir()
        conversation_ids = [
            path.split('/')[-2]
            for path in self.file_store.list(metadata_dir)
            if not path.startswith(f'{metadata_dir}/.')
        ]
        num_conversations = len(conversation_ids)
        start = page_id_to_offset(page_id)
        end = min(limit + start, num_conversations)
        conversation_ids = conversation_ids[start:end]
        conversations = []
        for conversation_id in conversation_ids:
            try:
                conversations.append(await self.get_metadata(conversation_id))
            except Exception:
                logger.warning(
                    f'Error loading conversation: {conversation_id}',
                    exc_info=True,
                    stack_info=True,
                )
        next_page_id = offset_to_page_id(end, end < num_conversations)
        return ConversationMetadataResultSet(conversations, next_page_id)
        
    def get_conversation_metadata_dir(self) -> str:
        return CONVERSATION_BASE_DIR

    def get_conversation_metadata_filename(self, conversation_id: str) -> str:
        return get_conversation_metadata_filename(conversation_id)

    @classmethod
    async def get_instance(cls, config: AppConfig, token: str | None):
        file_store = get_file_store(config.file_store, config.file_store_path)
        return FileConversationStore(file_store)
