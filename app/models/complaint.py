from datetime import datetime
from app import db
from app.models.base import BaseModel


class ComplaintStatus:
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_FOR_CUSTOMER = "WAITING_FOR_CUSTOMER"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class ComplaintPriority:
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class Complaint(BaseModel):
    __tablename__ = "complaints"

    id = db.Column(db.Integer, primary_key=True)
    ticket_number = db.Column(db.String(30), unique=True, nullable=False, index=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    assigned_employee_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)

    subject = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False, default="GENERAL")

    priority = db.Column(db.String(20), nullable=False, default=ComplaintPriority.MEDIUM)
    status = db.Column(db.String(30), nullable=False, default=ComplaintStatus.OPEN)

    internal_notes = db.Column(db.Text, nullable=True)
    resolution = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    customer = db.relationship("User", foreign_keys=[customer_id], backref="complaints_submitted")
    assigned_employee = db.relationship("User", foreign_keys=[assigned_employee_id], backref="complaints_assigned")

    def to_dict(self):
        return {
            "id": self.id,
            "ticket_number": self.ticket_number,
            "customer_id": self.customer_id,
            "customer_name": self.customer.full_name if self.customer else None,
            "assigned_employee_id": self.assigned_employee_id,
            "assigned_employee_name": self.assigned_employee.full_name if self.assigned_employee else None,
            "subject": self.subject,
            "description": self.description,
            "category": self.category,
            "priority": self.priority,
            "status": self.status,
            "internal_notes": self.internal_notes,
            "resolution": self.resolution,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
