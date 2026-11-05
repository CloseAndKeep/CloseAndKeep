"""Gift note constraints shared by CSV import, API validation, and CRM auto-order.

Crumbl's delivery checkout caps the printed gift note at 150 characters (sticker /
enclosure). CloseAndKeep keeps the same budget so notes fit bakery fulfillment,
including Levain fallback when an address is out of Crumbl delivery.
"""

GIFT_NOTE_MAX_LENGTH = 150
