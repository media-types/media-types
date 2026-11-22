This file summarizes the major and interesting changes for each release. For a
detailed list of changes, please see the git history.

2026.11.23
----------

* Parse registration and last updated dates.
  Add a `Registered` and `Last Updated` column to the CSV files.
* add several new media types to the personal and vendor trees:
  * `application/prs.ktb+zip`
  * `application/prs.zbook`
  * `application/vnd.BCG.TrustDeclaration`
  * `application/vnd.codynamicslab.latch`
  * `application/vnd.codynamicslab.latchdoc`
  * `application/vnd.colabox.fppd+json`
  * `application/vnd.emirian.blueprint`
  * `application/vnd.geovirtuallis.geov+zip`
  * `application/vnd.ibus+json`
  * `application/vnd.idop+zip`
  * `application/vnd.jupiter.jdx+json`
  * `application/vnd.krypteon.krpt`
  * `application/vnd.mcap`
  * `application/vnd.ngdtuanh.abook+zip`
  * `application/vnd.ngdtuanh.abookproj+zip`
  * `application/vnd.pebblestream.psosf+zip`
  * `application/vnd.penguin-pn.theuip`
  * `application/vnd.quantumsequrity.qnsqy`
  * `audio/prs.elupon-eua`
  * `image/vnd.imgformats.ssimf`
  * `model/vnd.pygrassreal.py3s`
  * `model/vnd.pygrassreal.py4s`
  * `text/prs.mtsv`
  * `text/prs.rowih`
  * `text/vnd.geml`

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
