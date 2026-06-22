# MVCC

MiniDB stores row versions with timestamps so reads can use a snapshot view while writes create new versions.

This is a simplified MVCC model:

- each version has a commit timestamp
- transactions track a snapshot timestamp
- readers see committed versions at or before their snapshot

