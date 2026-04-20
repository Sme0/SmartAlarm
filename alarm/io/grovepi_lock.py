from threading import RLock

# Shared lock to serialize GrovePi I/O across threads/components.
grovepi_lock = RLock()

