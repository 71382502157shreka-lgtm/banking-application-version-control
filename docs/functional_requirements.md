# Functional Requirements

- FR1: Users can register, log in, and log out.
- FR2: Customers can open accounts, deposit, withdraw, and transfer funds.
- FR3: Customers can add, edit, and deactivate beneficiaries.
- FR4: Every account/beneficiary/profile change produces a new version
  record with old and new state.
- FR5: Users can view the full version history of an entity.
- FR6: Users can compare any two versions of the same entity and see which
  fields were added, removed, modified, or unchanged.
- FR7: Every trackable action produces an audit log entry with actor, IP
  address, and timestamp.
- FR8: Admins can restore a non-financial record to a prior version.
- FR9: Financial transactions can be reversed but never edited or deleted.
- FR10: Access to each page/endpoint is restricted by role.
