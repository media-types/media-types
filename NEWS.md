This file summarizes the major and interesting changes for each release. For a
detailed list of changes, please see the git history.

2026.10.09
----------

* add several new media types to the vendor tree:
  * `application/vnd.fiduswriter.book+zip`
  * `application/vnd.fiduswriter.template+zip`
  * `application/vnd.excelano.slipcase+zip`
  * `model/vnd.sdf3d.s3d`
  * `application/vnd.godot.project.binary`
  * `application/vnd.godot.project.text`
  * `application/vnd.godot.resource.binary`
  * `application/vnd.godot.resource.text`
  * `application/vnd.drawoble.drawing+zip`
  * `application/vnd.fabylon.book`
  * `application/vnd.nnu.profile+json`
  * `application/vnd.aethel.package`
  * `application/vnd.nanorix.auditproof+json`
  * `application/vnd.dai`
  * `application/vnd.emilia.authorization-evidence-challenge+json`
  * `application/vnd.majikah.mjksmap`

2026.09.09
----------

* Parse intended usage and add an `Intended Usage` column to the CSV files
* reference RFC Errata 9028 in `application/tzif-leap`
* obsolete `application/vnd.edulith.edux+json`
* update `application/v3c` to RFC10034
* add `application/vnd.fiduswriter+zip`
* add `application/vnd.prml+yaml`
* scripts/generate_iana_csv.py: fix returning failure in
  `add_additional_information`

2026.08.21
----------

* Rename `unique` to `primary`. The CSV column is called
  `Primary File Extensions` now.

2026.08.19
----------

* Initial release
