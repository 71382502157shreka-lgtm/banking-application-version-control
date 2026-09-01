# Problem Statement

Banking systems store highly sensitive, high-consequence data — account
balances, beneficiary details, transaction records. Most academic banking
demos implement CRUD operations only, with no way to answer basic audit
questions: *Who changed this record? When? What did it look like before?*

This is a real gap. Regulators and internal risk teams require banks to
reconstruct the history of any account or profile change. Financial
transactions in particular must never be silently edited or deleted — a
correction must itself be a new, traceable event.

This project addresses that gap by building a banking application where
version history and audit logging are first-class, database-level features
rather than an afterthought bolted on with Git or manual logging.
