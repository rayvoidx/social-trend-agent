"""
Human-in-the-loop 워크플로우 관리

기능:
- 상태 머신 기반 워크플로우
- 검토/승인 프로세스
- 알림 통합
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


# =============================================================================
# Status Definitions
# =============================================================================

class WorkflowStatus(str, Enum):
    """워크플로우 상태."""
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    REVISION_REQUESTED = "revision_requested"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ReviewAction(str, Enum):
    """검토 액션."""
    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_REVISION = "request_revision"
    ESCALATE = "escalate"


# Valid state transitions
VALID_TRANSITIONS = {
    WorkflowStatus.DRAFT: [
        WorkflowStatus.PENDING_REVIEW,
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.PENDING_REVIEW: [
        WorkflowStatus.IN_REVIEW,
        WorkflowStatus.DRAFT,
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.IN_REVIEW: [
        WorkflowStatus.APPROVED,
        WorkflowStatus.REJECTED,
        WorkflowStatus.REVISION_REQUESTED,
    ],
    WorkflowStatus.APPROVED: [
        WorkflowStatus.PUBLISHED,
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.REJECTED: [
        WorkflowStatus.DRAFT,
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.REVISION_REQUESTED: [
        WorkflowStatus.DRAFT,
        WorkflowStatus.PENDING_REVIEW,
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.PUBLISHED: [
        WorkflowStatus.ARCHIVED,
    ],
    WorkflowStatus.ARCHIVED: [],
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class ReviewComment:
    """검토 코멘트."""
    reviewer: str
    comment: str
    created_at: float = field(default_factory=time.time)
    action: Optional[ReviewAction] = None


@dataclass
class WorkflowItem:
    """워크플로우 아이템."""
    id: str
    type: str  # insight, mission, etc.
    status: WorkflowStatus = WorkflowStatus.DRAFT
    data: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    created_by: str = "system"
    assigned_to: Optional[str] = None
    review_comments: List[ReviewComment] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type,
            "status": self.status.value,
            "data": self.data,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "created_by": self.created_by,
            "assigned_to": self.assigned_to,
            "review_comments": [
                {
                    "reviewer": c.reviewer,
                    "comment": c.comment,
                    "created_at": c.created_at,
                    "action": c.action.value if c.action else None,
                }
                for c in self.review_comments
            ],
            "metadata": self.metadata,
        }


# =============================================================================
# Workflow Manager
# =============================================================================

class WorkflowManager:
    """
    워크플로우 관리자.

    Human-in-the-loop 프로세스를 관리합니다.
    """

    def __init__(self):
        self._items: Dict[str, WorkflowItem] = {}
        self._hooks: Dict[str, List[Callable]] = {
            "on_status_change": [],
            "on_review_submit": [],
            "on_publish": [],
        }

    def create_item(
        self,
        id: str,
        type: str,
        data: Dict[str, Any],
        created_by: str = "system",
        auto_submit: bool = False
    ) -> WorkflowItem:
        """
        새 워크플로우 아이템 생성.

        Args:
            id: 아이템 ID
            type: 아이템 타입 (insight, mission)
            data: 아이템 데이터
            created_by: 생성자
            auto_submit: 자동으로 검토 요청

        Returns:
            생성된 WorkflowItem
        """
        item = WorkflowItem(
            id=id,
            type=type,
            data=data,
            created_by=created_by,
        )

        self._items[id] = item
        logger.info(f"Created workflow item: {id} ({type})")

        if auto_submit:
            self.submit_for_review(id)

        return item

    def get_item(self, id: str) -> Optional[WorkflowItem]:
        """아이템 조회."""
        return self._items.get(id)

    def update_item_data(
        self,
        id: str,
        data: Dict[str, Any]
    ) -> Optional[WorkflowItem]:
        """아이템 데이터 업데이트."""
        item = self._items.get(id)
        if not item:
            return None

        item.data.update(data)
        item.updated_at = time.time()
        return item

    def transition_status(
        self,
        id: str,
        new_status: WorkflowStatus,
        comment: Optional[str] = None,
        actor: str = "system"
    ) -> bool:
        """
        상태 전이.

        Args:
            id: 아이템 ID
            new_status: 새 상태
            comment: 코멘트
            actor: 수행자

        Returns:
            전이 성공 여부
        """
        item = self._items.get(id)
        if not item:
            logger.error(f"Item not found: {id}")
            return False

        # Validate transition
        valid_next = VALID_TRANSITIONS.get(item.status, [])
        if new_status not in valid_next:
            logger.error(
                f"Invalid transition: {item.status.value} -> {new_status.value}"
            )
            return False

        old_status = item.status
        item.status = new_status
        item.updated_at = time.time()

        if comment:
            item.review_comments.append(
                ReviewComment(reviewer=actor, comment=comment)
            )

        logger.info(f"Status transition: {id} {old_status.value} -> {new_status.value}")

        # Trigger hooks
        self._trigger_hooks("on_status_change", item, old_status, new_status)

        return True

    def submit_for_review(
        self,
        id: str,
        assignee: Optional[str] = None
    ) -> bool:
        """검토 요청 제출."""
        item = self._items.get(id)
        if not item:
            return False

        if item.status != WorkflowStatus.DRAFT:
            logger.warning(f"Item {id} is not in draft status")
            return False

        item.assigned_to = assignee
        success = self.transition_status(
            id,
            WorkflowStatus.PENDING_REVIEW,
            "Submitted for review"
        )

        if success:
            self._send_notification(
                "review_requested",
                item,
                assignee
            )

        return success

    def start_review(self, id: str, reviewer: str) -> bool:
        """검토 시작."""
        item = self._items.get(id)
        if not item:
            return False

        item.assigned_to = reviewer
        return self.transition_status(
            id,
            WorkflowStatus.IN_REVIEW,
            f"Review started by {reviewer}",
            actor=reviewer
        )

    def submit_review(
        self,
        id: str,
        action: ReviewAction,
        comment: str,
        reviewer: str
    ) -> bool:
        """
        검토 결과 제출.

        Args:
            id: 아이템 ID
            action: 검토 액션
            comment: 검토 코멘트
            reviewer: 검토자

        Returns:
            성공 여부
        """
        item = self._items.get(id)
        if not item:
            return False

        if item.status != WorkflowStatus.IN_REVIEW:
            logger.warning(f"Item {id} is not in review")
            return False

        # Add review comment
        item.review_comments.append(
            ReviewComment(
                reviewer=reviewer,
                comment=comment,
                action=action
            )
        )

        # Determine new status
        status_map = {
            ReviewAction.APPROVE: WorkflowStatus.APPROVED,
            ReviewAction.REJECT: WorkflowStatus.REJECTED,
            ReviewAction.REQUEST_REVISION: WorkflowStatus.REVISION_REQUESTED,
            ReviewAction.ESCALATE: WorkflowStatus.PENDING_REVIEW,
        }

        new_status = status_map.get(action)
        if not new_status:
            return False

        success = self.transition_status(id, new_status, comment, reviewer)

        if success:
            self._trigger_hooks("on_review_submit", item, action, reviewer)
            self._send_notification(
                f"review_{action.value}",
                item,
                item.created_by
            )

        return success

    def publish(self, id: str, publisher: str = "system") -> bool:
        """아이템 발행."""
        item = self._items.get(id)
        if not item:
            return False

        success = self.transition_status(
            id,
            WorkflowStatus.PUBLISHED,
            f"Published by {publisher}",
            publisher
        )

        if success:
            self._trigger_hooks("on_publish", item)

        return success

    def archive(self, id: str, reason: str = "") -> bool:
        """아이템 아카이브."""
        return self.transition_status(
            id,
            WorkflowStatus.ARCHIVED,
            f"Archived: {reason}"
        )

    # =========================================================================
    # Query Methods
    # =========================================================================

    def list_items(
        self,
        status: Optional[WorkflowStatus] = None,
        type: Optional[str] = None,
        assigned_to: Optional[str] = None
    ) -> List[WorkflowItem]:
        """아이템 목록 조회."""
        items = list(self._items.values())

        if status:
            items = [i for i in items if i.status == status]
        if type:
            items = [i for i in items if i.type == type]
        if assigned_to:
            items = [i for i in items if i.assigned_to == assigned_to]

        return sorted(items, key=lambda x: x.updated_at, reverse=True)

    def get_pending_reviews(self, reviewer: Optional[str] = None) -> List[WorkflowItem]:
        """검토 대기 아이템 조회."""
        items = self.list_items(status=WorkflowStatus.PENDING_REVIEW)
        if reviewer:
            items = [i for i in items if i.assigned_to == reviewer or i.assigned_to is None]
        return items

    def get_review_history(self, id: str) -> List[Dict[str, Any]]:
        """검토 이력 조회."""
        item = self._items.get(id)
        if not item:
            return []

        return [
            {
                "reviewer": c.reviewer,
                "comment": c.comment,
                "action": c.action.value if c.action else None,
                "created_at": c.created_at,
            }
            for c in item.review_comments
        ]

    # =========================================================================
    # Hooks and Notifications
    # =========================================================================

    def register_hook(self, event: str, callback: Callable):
        """이벤트 훅 등록."""
        if event in self._hooks:
            self._hooks[event].append(callback)

    def _trigger_hooks(self, event: str, *args):
        """훅 트리거."""
        for callback in self._hooks.get(event, []):
            try:
                callback(*args)
            except Exception as e:
                logger.error(f"Hook error ({event}): {e}")

    def _send_notification(
        self,
        notification_type: str,
        item: WorkflowItem,
        recipient: Optional[str] = None
    ):
        """알림 전송."""
        # Slack notification
        slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        if slack_webhook:
            self._send_slack_notification(notification_type, item)

        # Email notification
        if recipient and os.getenv("SMTP_HOST"):
            self._send_email_notification(notification_type, item, recipient)

        logger.info(f"Notification sent: {notification_type} for {item.id}")

    def _send_slack_notification(
        self,
        notification_type: str,
        item: WorkflowItem
    ):
        """Slack 알림 전송."""
        try:
            import requests

            webhook_url = os.getenv("SLACK_WEBHOOK_URL")
            if not webhook_url:
                return

            # Format message
            messages = {
                "review_requested": f"🔔 검토 요청: {item.type} `{item.id}`",
                "review_approve": f"✅ 승인됨: {item.type} `{item.id}`",
                "review_reject": f"❌ 거부됨: {item.type} `{item.id}`",
                "review_request_revision": f"📝 수정 요청: {item.type} `{item.id}`",
            }

            message = messages.get(
                notification_type,
                f"📋 {notification_type}: {item.type} `{item.id}`"
            )

            payload = {
                "text": message,
                "attachments": [
                    {
                        "color": "#36a64f" if "approve" in notification_type else "#ff0000",
                        "fields": [
                            {"title": "Status", "value": item.status.value, "short": True},
                            {"title": "Assigned To", "value": item.assigned_to or "Unassigned", "short": True},
                        ]
                    }
                ]
            }

            requests.post(webhook_url, json=payload, timeout=5)

        except Exception as e:
            logger.error(f"Slack notification failed: {e}")

    def _send_email_notification(
        self,
        notification_type: str,
        item: WorkflowItem,
        recipient: str
    ):
        """이메일 알림 전송."""
        # Implementation depends on email service
        pass


# =============================================================================
# Global Instance
# =============================================================================

_workflow_manager: Optional[WorkflowManager] = None


def get_workflow_manager() -> WorkflowManager:
    """Get workflow manager instance (singleton)."""
    global _workflow_manager
    if _workflow_manager is None:
        _workflow_manager = WorkflowManager()
    return _workflow_manager


# =============================================================================
# Helper Functions
# =============================================================================

def create_insight_workflow(
    insight_id: str,
    insight_data: Dict[str, Any],
    auto_submit: bool = True
) -> WorkflowItem:
    """인사이트 워크플로우 생성."""
    manager = get_workflow_manager()
    return manager.create_item(
        id=insight_id,
        type="insight",
        data=insight_data,
        auto_submit=auto_submit
    )


def create_mission_workflow(
    mission_id: str,
    mission_data: Dict[str, Any],
    auto_submit: bool = True
) -> WorkflowItem:
    """미션 워크플로우 생성."""
    manager = get_workflow_manager()
    return manager.create_item(
        id=mission_id,
        type="mission",
        data=mission_data,
        auto_submit=auto_submit
    )


def approve_item(id: str, reviewer: str, comment: str = "Approved") -> bool:
    """아이템 승인."""
    manager = get_workflow_manager()

    # Start review if pending
    item = manager.get_item(id)
    if item and item.status == WorkflowStatus.PENDING_REVIEW:
        manager.start_review(id, reviewer)

    return manager.submit_review(
        id,
        ReviewAction.APPROVE,
        comment,
        reviewer
    )


def reject_item(id: str, reviewer: str, comment: str) -> bool:
    """아이템 거부."""
    manager = get_workflow_manager()

    item = manager.get_item(id)
    if item and item.status == WorkflowStatus.PENDING_REVIEW:
        manager.start_review(id, reviewer)

    return manager.submit_review(
        id,
        ReviewAction.REJECT,
        comment,
        reviewer
    )


def request_revision(id: str, reviewer: str, comment: str) -> bool:
    """수정 요청."""
    manager = get_workflow_manager()

    item = manager.get_item(id)
    if item and item.status == WorkflowStatus.PENDING_REVIEW:
        manager.start_review(id, reviewer)

    return manager.submit_review(
        id,
        ReviewAction.REQUEST_REVISION,
        comment,
        reviewer
    )
