These layout measurements and Courier New regular/bold font subsets were
extracted from the user-supplied `res/Test-1.pdf`. `header.json` contains only
static headings and rules, with top-origin coordinates in PDF points. Employer,
year, employee, and financial values are drawn from the current snapshot.

The original report uses 6.9552-point body text and 9.9534-point titles on
1008 x 612-point landscape legal pages. Bundling its font subsets avoids an
operating-system font dependency. Characters absent from the supplied subsets
use standard PDF Courier at the same size, rather than disappearing.

Printed compensation groups include all source components: (4b) = AK + AM,
(4e) = AN + AP, (4h) = F + H, and (4k) = L + N. Other columns map directly
to the corresponding snapshot values. Totals are recalculated from these
groups; inconsistent sample amounts are not copied into new reports.

Full names wrap inside the name column. Original spellings and employee IDs
are retained in PDF note annotations; the source hash/profile is in document
metadata. A draft is marked on every sheet. As in the reference, the grand
total and end-of-report marker occupy a separate continuation sheet.
