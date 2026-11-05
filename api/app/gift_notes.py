"""Gift note constraints shared by CSV import, API validation, and CRM auto-order.

Gift notes are capped so they fit bakery checkout sticker / enclosure fields
(Crumbl first; Levain fallback when an address is out of Crumbl delivery).
"""

GIFT_NOTE_MAX_LENGTH = 105
