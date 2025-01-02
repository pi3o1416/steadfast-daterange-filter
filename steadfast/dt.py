"""
Common Datatypes
"""
from enum import Enum


class Status(Enum):
    """
    Product Status enum
    """
    ALL = "All"
    PENDING = "Pending"
    APPROVAL_PENDING = "Approval Pending"
    DELEVERED = "Delivered"
    PARTLY_DELIVERED = "Partly Delivered"
    CANCELLED = "Cancelled"
    IN_REVIEW = "In Review"
    PICK_N_DROP = "Pick-n-Drop"
