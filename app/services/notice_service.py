from datetime import datetime
from ..extensions import db
from ..models import FormalNotice


class NoticeService:

    @staticmethod
    def save_notice(current_user, data):
        vp_date = None
        vp_raw = (data.get("vp_date") or "").strip()
        if vp_raw:
            try:
                vp_date = datetime.strptime(vp_raw, "%Y-%m-%d").date()
            except ValueError:
                pass

        notice = FormalNotice(
            homeowner_id=current_user.id,
            developer_id=current_user.assigned_developer_id or None,
            buyer_name=(data.get("buyer_name") or "").strip()[:150],
            buyer_ic=(data.get("buyer_ic") or "").strip()[:20],
            buyer_address=(data.get("buyer_address") or "").strip(),
            buyer_contact=(data.get("buyer_contact") or "").strip()[:30],
            dev_name=(data.get("dev_name") or "").strip()[:150],
            dev_address=(data.get("dev_address") or "").strip(),
            project_name=(data.get("project_name") or "").strip()[:150],
            unit_no=(data.get("unit_no") or "").strip()[:100],
            vp_date=vp_date,
            spa_ref=(data.get("spa_ref") or "").strip()[:150],
            defects_json=data.get("defects") or [],
            letter_html=data.get("letter_html") or "",
        )

        db.session.add(notice)
        db.session.commit()
        return notice
