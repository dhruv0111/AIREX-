# Role & Permission Matrix — AIREX

This matrix is built **strictly from the PRD V1.0** (§7 Roles, §9, §10, AC-AUTH-006). No permissions are assumed. Where the PRD does not specify a role's permission for an action, the cell is marked **NS** (Not Specified) and cross-referenced to the [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md) (AMB-PERM-001).

## Roles (from §7)

| Role | Stated capabilities |
|------|---------------------|
| **Admin** | Create organizations; Manage users; Manage projects; Manage API keys; Configure integrations; Configure policies; View all reports |
| **Project Owner** | Create evaluations; Manage datasets; Configure models; Run experiments; Manage environments |
| **Engineer** | Run evaluations; Create test cases; View dashboards; Create experiments |
| **Viewer** | View dashboards; View reports; View experiment results |

---

## Matrix

Legend: ✅ = explicitly allowed by PRD · ❌ = explicitly denied by PRD · **NS** = not specified in PRD (must be clarified) · — = action does not apply to this role.

| Module | Action | Admin | Project Owner | Engineer | Viewer | Source |
|--------|--------|:-----:|:-------------:|:--------:|:------:|--------|
| **Organizations** | Create organization | ✅ | NS | NS | NS | §7 |
| | Invite users | ✅ | NS | ❌ (implied by "Manage users" = Admin only) | NS | §10 |
| | Remove users | ✅ | NS | NS | NS | §10 |
| | Change roles | ✅ | NS | NS | NS | §10 |
| | View organization settings | ✅ | NS | NS | NS | §10, §68 |
| | Edit organization settings | ✅ | NS | NS | NS | NS |
| **Projects** | Create project | ✅ | NS | NS | NS | §7, §11 |
| | Edit project | ✅ | NS | NS | NS | §11 |
| | Archive project | ✅ | NS | NS | NS | §11 |
| | Delete project (with confirmation) | ✅ | NS | NS | NS | §11 |
| | View project dashboard | ✅ | ✅ (View dashboards as Engineer; Owner implied) | ✅ | ✅ | §7, §69 |
| **API Keys** | Create/manage API keys | ✅ | NS | NS | NS | §7 |
| **Integrations** | Configure integrations | ✅ | NS | NS | NS | §7 |
| **Policies** | Configure policies (e.g., regression/quality gate thresholds) | ✅ | NS | NS | NS | §7 |
| **Models / Providers** | Configure models | NS | ✅ | NS | NS | §7 |
| | View models | ✅ | ✅ | ✅ | NS | §7 |
| **Datasets** | Manage datasets | NS | ✅ | NS | NS | §7 |
| | Modify datasets/evaluations | NS | ✅ | NS | ❌ | AC-AUTH-006 |
| **Test Cases** | Create test cases | NS | NS | ✅ | NS | §7 |
| **Evaluations** | Create evaluations | NS | ✅ | NS | NS | §7 |
| | Run evaluations | NS | ✅ (Run experiments) | ✅ | NS | §7 |
| | View evaluation results | ✅ | ✅ | ✅ | ✅ (View experiment results) | §7 |
| **Experiments** | Create experiments | NS | ✅ (Run experiments) | ✅ | NS | §7 |
| | Run experiments | NS | ✅ | NS | NS | §7 |
| | View experiment results | ✅ | ✅ | ✅ | ✅ | §7 |
| **Environments** | Manage environments | NS | ✅ | NS | NS | §7 |
| **Reports** | View all reports | ✅ | NS | NS | ✅ | §7 |
| | Generate reports | NS | NS | NS | NS | NS |
| **Dashboards** | View dashboards | ✅ | ✅ | ✅ | ✅ | §7 |
| **Audit Logs** | View audit logs | ✅ | NS | NS | NS | §68, §61 (security-sensitive events) |
| **Administration** | All admin functions | ✅ | NS | NS | NS | §7 |

---

## Explicit Permission Rules from ACs

| Rule ID | Rule | Roles affected |
|---------|------|----------------|
| AC-AUTH-005 | Users only access projects belonging to their organization | All |
| AC-AUTH-006 | Viewer must not modify datasets or evaluations | Viewer (❌ modify) |
| AC-SEC-001 | User A cannot retrieve Organization B data | All |
| AC-SEC-002 | Project IDs cannot be used to bypass authorization | All |
| AC-SEC-004 | Deleted users lose access immediately | All (removed users) |
| AC-SEC-005 | Audit logs cannot be modified by normal users | Non-admin (❌ modify) |

---

## Analysis: Permission Gaps (NS cells)

The PRD defines role *headline* capabilities but does **not** define a granular permission matrix. The following are explicitly **NS** and must be clarified before RBAC implementation (see AMB-PERM-001):

1. Whether Project Owner can create projects or only manage existing ones.
2. Whether Engineer can create datasets (vs. only test cases).
3. Whether Engineer can configure models (per §7, "Configure models" is listed under Project Owner only).
4. Whether Viewer can view datasets, models, traces, or audit logs.
5. Whether Admin can run evaluations.
6. Report generation and export permissions.
7. Whether roles are per-organization, per-project, or both (project-level permissions are mentioned in §9 but not defined).
8. Human review permissions (which roles may override AI judgments).
9. Test approval permissions (approve/reject generated tests — AC-TESTGEN-004).
10. Alert rule creation permissions.
11. Archive vs. delete authorization.
12. Research workspace access (which roles may create research experiments).

All gaps are logged in the [`AMBIGUITY_REGISTER.md`](./AMBIGUITY_REGISTER.md) as **AMB-PERM-001** and sub-items.
