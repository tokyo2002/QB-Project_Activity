# App map

The sub-processes in the Project Activity app (`bg86uwfcw`) and the tables each one uses. This is a first pass, taken from the table list on 2026-10-14. The grouping is a draft and will be refined.

## 1. Time tracking

| Table | ID | Notes |
|---|---|---|
| Employees | `bhm98v33q` | Updated by a pipeline |
| Time Cards | `bhm9822gc` | About 550k records |
| Weeks | `bvpp7r2kk` | |
| Users | `bntsrn9zw` | |
| Departments | `bvwyyzgqd` | Connected table from the Users app |
| Disciplines | `bv96f99xq` | Connected table from the Users app |
| Department Managers | `bvwyzsquk` | Connected table from the Users app |

## 2. Projects and tasks (core)

| Table | ID | Notes |
|---|---|---|
| Projects | `bpaz4pr6u` | |
| Tasks | `biwfb28d9` | |
| Business Units | `bv96ejeh7` | |
| Branch Plants | `bvz6v6tg7` | |
| Project Financials | `bv5z9ted3` | |
| Customer Transmittals | `br5sx4bn2` | |
| Meeting Minutes | `bmvvfeiyd` | |
| Meeting Minute Tasks | `bpjpipp4c` | |

## 3. Change orders

| Table | ID | Notes |
|---|---|---|
| Change Orders | `bu3n55sk4` | |
| Change Order Parts | `bu3n6rxzk` | |
| Change Order Documents | `bu3n63a3y` | |
| Change Order Roles | `bvbjep2mj` | |
| Project - Change Order Counter | `bu3rdm8xh` | |
| Audit Logs | `bva835mcw` | Child of Change Orders and Tasks |

## 4. NPD (new product development)

| Table | ID | Notes |
|---|---|---|
| NPD Project Tracking | `bvaesxd8r` | |
| NPD Investments | `bv6kbiwnp` | Used by the NPD Account Sync pipeline (see `pipelines/`) |
| NPD Expenses | `bwa9wjt5w` | JDE subledger records |
| NPD Proposed Hours | `bvpdz8n8b` | |
| User NPD Projects | `bvrmztv29` | |

## 5. Products and manufacturing

| Table | ID | Notes |
|---|---|---|
| Products | `bg86uurfj` | |
| Part Numbers | `bnvyujkqr` | |
| Item Masters | `btzezc9nj` | Connected table from the Item Numbers app |
| SAP Part Number | `bv4gt5xd8` | |
| Work Orders | `bnuk3qri9` | |
| Work Orders 2 | `bs3nmfx3p` | |
| MFG Schedule | `bnuk4hrfp` | |
| PNDemandSchedule | `bpnu9aiex` | |
| Manufacturing Plan | `bv45x6ges` | |
| Project CSR | `bmvmm9jab` | Used by Field Engineering |
| Praforms PQPs | `bi3razv43` | |

## 6. India and regional projects

| Table | ID | Notes |
|---|---|---|
| Hyderabad Projects | `bv8hjihyy` | |
| Howden India Projects | `bwc2awnfh` | |
| Project Progress Tracker_Sricity | `bwdjpzfid` | |
| Localization Projects | `bv6q534ae` | |

## 7. Sales and customers

| Table | ID | Notes |
|---|---|---|
| Customers | `bpvpfz5bp` | |
| Opportunities | `bnrp2b89r` | |
| SO SOLDTO | `bpvpfuva9` | Description says current usage unknown |
| Sales Force Users | `br6rr5vrd` | |

## 8. Engineering resource hub

| Table | ID | Notes |
|---|---|---|
| GERH - Adhoc Requests | `bvhzhaa9x` | Mirror of Global Engineering Resource Hub ad hoc requests |

## 9. Admin and security

| Table | ID | Notes |
|---|---|---|
| Access Roles | `bvdgwgcz7` | |
| User Access Roles | `bvdgwrnnj` | |
| Application Options - Admin | `bvr7txty8` | |
| Change Log | `bv54hme8z` | Changes made to the app |

## Open questions

- Is the grouping right? Some tables may belong to a different group or to more than one.
- Products, Tasks, Time Cards, Part Numbers and MFG Schedule have relationships to parent tables that aren't in this app, such as `bpuyeqk77`, `biiaqic4r`, `bsyw23iwd` and `bm2z7dk2m`, and some that the API reports as unknown. These are either cross-app links or leftovers from deleted tables.
- Some tables may no longer be used. Record counts and last-modified dates would show which.
