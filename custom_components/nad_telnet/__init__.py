"""NAD receivers over a persistent telnet connection (media_player platform only).

Replaces the core `nad` integration for the T758: that one reads replies in
order, while the receiver also pushes unsolicited changes on the same
connection, so its answers drift (power flips on/off, source goes empty).
"""
