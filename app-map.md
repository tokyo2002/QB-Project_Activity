# App map

The sub-processes in the Project Activity app (`bg86uwfcw`) and the tables each one uses. This is a first pass, taken from the table list on 2026-10-14. The grouping is a draft and will be refined.

## 1. Time tracking

| Table | ID | Notes |
|---|---|---|
| Employees | `bhm98v33q` | Updated by a pipeline |
| Time Cards | `bhm9822gc` | About 125k records. Record IDs run past 555,000 because many cards have been deleted |
| Time Card Days | `bwe8cjimn` | New 2026-10-14. 7 records per time card, for accounting-period hours. See `pipelines/` |
| Weeks | `bvpp7r2kk` | |
| Users | `bntsrn9zw` | |
| Departments | `bvwyyzgqd` | Connected table from the Users app |
| Disciplines | `bv96f99xq` | Connected table from the Users app |
| Department Managers | `bvwyzsquk` | Connected table from the Users app |

### What makes a Time Card

A Time Card is **one person's hours against one piece of work for one week** (Sunday to Saturday). Someone working on three things in a week has three cards for that week. Nothing in Quickbase enforces this. No field is set as Required or Unique besides Record ID#.

**What every card has**

Fields that may not be required, but are essential defining a TIme Card

- Employee
- Time Card Type
- Time Card Title
- Date
- Week Beginning calculated from [Date]
- Sunday
- Monday
- Tuesday
- Wednesday
- Thursday
- Friday
- Saturday


| Part | Fields | Notes |
|---|---|---|
| Who | Related Employee (15, user field). Employee (17) is a lookup of it | Employee details (name, department, location) are lookups from Employees, so they show the person's *current* values, not the values at the time |
| When | Date (9), the one date the user picks. Week Beginning (8) = `FirstDayOfWeek([Date])`, and Week Ending (7) = Week Beginning + 6 | **Date is the only stored date.** Week Beginning and Week Ending are formulas. Sunday - Day … Saturday - Day (315–321) are formulas giving each column's date |
| Hours | Sunday (23), Monday (10), Tuesday (11), Wednesday (12), Thursday (13), Friday (14), Saturday (24) | Total Regular Hours (6) is the sum of the seven. Total Hours (183) = Total Regular Hours |
| What the work is | **One** of several reference fields (below) | The card's **Time Card Type** (151) is worked out from which reference field is filled in |

**What the work is: Time Card Type.** Time Card Type (151) is a formula. It checks the reference fields in a fixed order and stops at the first one that's filled in. Time Card Title (137) then builds a label for that type, such as "ESR #123 – …" or "Project – Task".

| Time Card Type | Set when | 2026 cards | 2026 hours |
|---|---|---|---|
| Administrative / Support / Packet Checking / CNC Programming | Related Task (57) is an Administrative task. The task name picks which one | 4,888 | 33,970 |
| Project Task | Related Project (208) and Related Task (57) | 3,917 | 28,029 |
| Project | Related Project (208) with no task | 2,432 | 12,687 |
| NPD Project | Related NPD Project (266) | 2,235 | 25,267 |
| Product Task | Related Product (18) and Related Task (57) | 2,178 | 23,155 |
| Hyderabad Project | Related Hyderabad Project (272) | 1,268 | 3,355 |
| Product | Related Product (18) with no task | 990 | 9,393 |
| Howden India Project | Related Howden India Project (301) | 229 | 1,436 |
| Miscellaneous Task | Related Task (57), any other task type | 121 | 251 |
| Engineering Service Request | Related Engineering Service Request (142) | 108 | 196 |
| Engineering Change Request / Temporary Design Deviation | Related ECR/TDD (118), split on ECR/TDD - Type | 17 | 70 |
| Project Service | Related Service Ticket (184) | 12 | 22 |
| VIP Design Worksheet / Document Inquiry / Vaporizer Design Worksheet | Related VIP Order Worksheet (247), Document Inquiry (163), Vaporizer WorkSheet (249) | 5 | 6 |
| Unknown Time Card Type | None of the above | 14 | 488 |

The 2026 counts cover cards created from 2026-01-01 to 2026-10-14: 18,414 cards. The checks run in this order: ESR → Vaporizer → VIP → Document Inquiry → ECR/TDD → Product (+Task) → Project (+Task) → Hyderabad → Howden India → Task types → NPD → Service Ticket. A card with more than one reference filled in gets the first type in that order.

**Business unit and project depend on the type.** No single field gives a card's BU and project for every type:
- **Project Name (300)** and the new **Business Unit** fields (296, 297, 309) come through **Related Task → Project**. Cards with no task (NPD Project, Product, Project) have neither.
- **Legacy Business Unit (128)** is a formula built from Product and Task. It covers most types, but not most Product and Product Task cards.

The hours affected are measured in the Time Card Days build sheet, O1.

**Locking.** Time Card Age (303) is the number of days since Week Beginning. Once it's over 14, **Timecard Locked** (307) turns true and the card can no longer be edited, unless someone checks **Unlock Timecard** (306).

**Deleting.** Checking **Delete Record** (268) starts the Delete Record Pipeline. That Pipeline first deletes the card's Time Card Days, then deletes the card.

**Derived records.** Each card in the Time Card Days window (Week Ending on or after 2026-08-26) has 7 day records, written by Pipeline A. The fields 326–328 on the card check those records against the card.

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
