import io
import hashlib
import json
import re
import zipfile
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import or_, func
from sqlalchemy.orm import Session

from app.data.models import (
    VaultNote,
    VaultLink,
    VaultProposal,
)


WIKILINK_RE = re.compile(r"\[\[(.+?)\]\]")


def _slugify(text: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9\s-]", "", text).strip().lower()
    slug = re.sub(r"[\s_-]+", "-", slug)
    return slug or "note"


class VaultService:
    def __init__(self, db: Session, user_id: str):
        self.db = db
        self.user_id = user_id

    def _unique_slug(self, title: str) -> str:
        base = _slugify(title)
        slug = base
        i = 2
        while self.db.query(VaultNote).filter(
            VaultNote.user_id == self.user_id,
            VaultNote.slug == slug
        ).first():
            slug = f"{base}-{i}"
            i += 1
        return slug

    @staticmethod
    def _normalize_dedupe_text(value: Optional[str]) -> str:
        if not value:
            return ""
        normalized = re.sub(r"[^a-z0-9\s]", " ", value.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        return normalized

    def _build_proposal_dedupe_key(
        self,
        proposal_type: str,
        proposed_data: Dict[str, Any],
        source_type: str,
        source_id: Optional[str] = None,
    ) -> str:
        canonical = {
            "user_id": self.user_id,
            "proposal_type": proposal_type,
            "source_type": source_type or "",
            "source_id": source_id or "",
            "note_type": self._normalize_dedupe_text(str(proposed_data.get("note_type", ""))),
            "title": self._normalize_dedupe_text(str(proposed_data.get("title", ""))),
            "body": self._normalize_dedupe_text(str(proposed_data.get("body", ""))),
            "canonical_email": self._normalize_dedupe_text(str(proposed_data.get("canonical_email", ""))),
        }
        packed = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(packed.encode("utf-8")).hexdigest()

    def create_note(
        self,
        note_type: str,
        title: str,
        body: str = "",
        frontmatter: Optional[Dict[str, Any]] = None,
        canonical_email: Optional[str] = None,
        source: str = "manual",
        confidence: float = 1.0,
    ) -> VaultNote:
        slug = self._unique_slug(title)
        note = VaultNote(
            user_id=self.user_id,
            slug=slug,
            note_type=note_type,
            title=title,
            frontmatter=frontmatter or {},
            body=body or "",
            canonical_email=canonical_email.lower() if canonical_email else None,
            aliases=[],
            source=source,
            confidence=confidence,
            status="active",
            pinned=False,
        )
        self.db.add(note)
        self.db.commit()
        self.db.refresh(note)
        self.sync_links_from_body(note.id)
        return note

    def get_note(self, note_id: int) -> Optional[VaultNote]:
        return self.db.query(VaultNote).filter(
            VaultNote.id == note_id,
            VaultNote.user_id == self.user_id
        ).first()

    def get_note_by_slug(self, slug: str) -> Optional[VaultNote]:
        return self.db.query(VaultNote).filter(
            VaultNote.slug == slug,
            VaultNote.user_id == self.user_id
        ).first()

    def get_note_by_email(self, email: str) -> Optional[VaultNote]:
        return self.db.query(VaultNote).filter(
            VaultNote.user_id == self.user_id,
            VaultNote.canonical_email == email.lower()
        ).first()

    def update_note(
        self,
        note_id: int,
        title: Optional[str] = None,
        body: Optional[str] = None,
        frontmatter: Optional[Dict[str, Any]] = None,
        pinned: Optional[bool] = None,
        status: Optional[str] = None,
    ) -> Optional[VaultNote]:
        note = self.get_note(note_id)
        if not note:
            return None
        if title is not None and title != note.title:
            note.title = title
        if body is not None:
            note.body = body
        if frontmatter is not None:
            note.frontmatter = frontmatter
        if pinned is not None:
            note.pinned = pinned
        if status is not None:
            note.status = status
        note.updated_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(note)
        if body is not None:
            self.sync_links_from_body(note.id)
        return note

    def list_notes(
        self, note_type: Optional[str] = None, limit: int = 50, offset: int = 0
    ) -> Tuple[List[VaultNote], int]:
        q = self.db.query(VaultNote).filter(VaultNote.user_id == self.user_id)
        if note_type:
            q = q.filter(VaultNote.note_type == note_type)
        total = q.count()
        notes = q.order_by(VaultNote.updated_at.desc()).offset(offset).limit(limit).all()
        return notes, total

    def search_notes(
        self, query: str, note_type: Optional[str] = None, limit: int = 20
    ) -> List[VaultNote]:
        q = self.db.query(VaultNote).filter(VaultNote.user_id == self.user_id)
        if note_type:
            q = q.filter(VaultNote.note_type == note_type)
        like_query = f"%{query}%"
        q = q.filter(or_(VaultNote.title.ilike(like_query), VaultNote.body.ilike(like_query)))
        return q.order_by(VaultNote.updated_at.desc()).limit(limit).all()

    def archive_note(self, note_id: int) -> Optional[VaultNote]:
        return self.update_note(note_id, status="archived")

    def add_link(
        self,
        source_id: int,
        target_id: int,
        link_type: str = "reference",
        context: Optional[str] = None,
    ) -> Optional[VaultLink]:
        if source_id == target_id:
            return None
        existing = self.db.query(VaultLink).filter(
            VaultLink.user_id == self.user_id,
            VaultLink.source_note_id == source_id,
            VaultLink.target_note_id == target_id,
            VaultLink.link_type == link_type,
        ).first()
        if existing:
            return existing
        link = VaultLink(
            user_id=self.user_id,
            source_note_id=source_id,
            target_note_id=target_id,
            link_type=link_type,
            context=context,
        )
        self.db.add(link)
        self.db.commit()
        self.db.refresh(link)
        return link

    def get_neighbors(self, note_id: int, depth: int = 1) -> List[VaultNote]:
        if depth != 1:
            depth = 1
        links = self.db.query(VaultLink).filter(
            VaultLink.user_id == self.user_id,
            or_(VaultLink.source_note_id == note_id, VaultLink.target_note_id == note_id)
        ).all()
        ids = set()
        for link in links:
            if link.source_note_id != note_id:
                ids.add(link.source_note_id)
            if link.target_note_id != note_id:
                ids.add(link.target_note_id)
        if not ids:
            return []
        return self.db.query(VaultNote).filter(
            VaultNote.user_id == self.user_id,
            VaultNote.id.in_(ids)
        ).all()

    def sync_links_from_body(self, note_id: int) -> None:
        note = self.get_note(note_id)
        if not note:
            return
        # Remove existing reference links from this note and recreate
        self.db.query(VaultLink).filter(
            VaultLink.user_id == self.user_id,
            VaultLink.source_note_id == note_id,
            VaultLink.link_type == "reference",
        ).delete()
        targets = {_slugify(m.group(1)) for m in WIKILINK_RE.finditer(note.body or "")}
        for target_slug in targets:
            target = self.get_note_by_slug(target_slug)
            if target:
                self.db.add(VaultLink(
                    user_id=self.user_id,
                    source_note_id=note_id,
                    target_note_id=target.id,
                    link_type="reference",
                ))
        self.db.commit()

    def render_note_as_markdown(self, note_id: int) -> str:
        note = self.get_note(note_id)
        if not note:
            return ""
        fm = note.frontmatter or {}
        lines = ["---"]
        for k, v in fm.items():
            lines.append(f"{k}: {v}")
        lines.append("---")
        lines.append("")
        lines.append(note.body or "")
        return "\n".join(lines)

    def export_vault(self) -> bytes:
        notes = self.db.query(VaultNote).filter(VaultNote.user_id == self.user_id).all()
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
            for note in notes:
                zf.writestr(f"{note.slug}.md", self.render_note_as_markdown(note.id))
        return buffer.getvalue()

    def list_proposals(self, status: str = "pending", limit: int = 50, offset: int = 0) -> Tuple[List[VaultProposal], int]:
        q = self.db.query(VaultProposal).filter(VaultProposal.user_id == self.user_id)
        if status:
            q = q.filter(VaultProposal.status == status)
        total = q.count()
        proposals = q.order_by(VaultProposal.created_at.desc()).offset(offset).limit(limit).all()
        return proposals, total

    def propose(
        self,
        proposal_type: str,
        proposed_data: Dict[str, Any],
        diff_summary: str,
        source_type: str,
        source_id: Optional[str] = None,
        confidence: float = 0.5,
        target_note_id: Optional[int] = None,
        dedupe_key: Optional[str] = None,
    ) -> VaultProposal:
        proposal_dedupe_key = dedupe_key or self._build_proposal_dedupe_key(
            proposal_type=proposal_type,
            proposed_data=proposed_data or {},
            source_type=source_type,
            source_id=source_id,
        )
        existing = self.db.query(VaultProposal).filter(
            VaultProposal.user_id == self.user_id,
            VaultProposal.dedupe_key == proposal_dedupe_key,
            VaultProposal.status.in_(["pending", "approved"]),
        ).order_by(VaultProposal.created_at.desc()).first()
        if existing:
            return existing

        proposal = VaultProposal(
            user_id=self.user_id,
            target_note_id=target_note_id,
            proposal_type=proposal_type,
            proposed_data=proposed_data,
            diff_summary=diff_summary,
            source_type=source_type,
            source_id=source_id,
            dedupe_key=proposal_dedupe_key,
            confidence=confidence,
            status="pending",
        )
        self.db.add(proposal)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def approve_proposal(self, proposal_id: int) -> Optional[VaultProposal]:
        proposal = self.db.query(VaultProposal).filter(
            VaultProposal.id == proposal_id,
            VaultProposal.user_id == self.user_id,
        ).first()
        if not proposal or proposal.status != "pending":
            return proposal

        data = proposal.proposed_data or {}
        if proposal.proposal_type == "create_note":
            created = self.create_note(
                note_type=data.get("note_type", "decision"),
                title=data.get("title", "Untitled"),
                body=data.get("body", ""),
                frontmatter=data.get("frontmatter", {}),
                canonical_email=data.get("canonical_email"),
                source=data.get("source", "email_extraction"),
                confidence=proposal.confidence,
            )
            proposal.target_note_id = created.id
        elif proposal.proposal_type == "update_note" and proposal.target_note_id:
            self.update_note(
                proposal.target_note_id,
                title=data.get("title"),
                body=data.get("body"),
                frontmatter=data.get("frontmatter"),
            )
        elif proposal.proposal_type == "add_link":
            self.add_link(
                source_id=data.get("source_note_id"),
                target_id=data.get("target_note_id"),
                link_type=data.get("link_type", "reference"),
                context=data.get("context"),
            )
        elif proposal.proposal_type == "update_frontmatter" and proposal.target_note_id:
            note = self.get_note(proposal.target_note_id)
            if note:
                fm = note.frontmatter or {}
                fm.update(data.get("frontmatter", {}))
                self.update_note(note.id, frontmatter=fm)

        proposal.status = "approved"
        proposal.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal

    def reject_proposal(self, proposal_id: int, reason: Optional[str], category: str) -> Optional[VaultProposal]:
        proposal = self.db.query(VaultProposal).filter(
            VaultProposal.id == proposal_id,
            VaultProposal.user_id == self.user_id,
        ).first()
        if not proposal or proposal.status != "pending":
            return proposal
        proposal.status = "rejected"
        proposal.rejection_reason = reason
        proposal.rejection_category = category
        proposal.reviewed_at = datetime.now(timezone.utc)
        self.db.commit()
        self.db.refresh(proposal)
        return proposal
