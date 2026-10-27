# Terrain Glow

Terrain Glow makes shaded-relief pictures and short clips of mountains, volcanoes, fjords and canyons.
Pick a place, a frame for a social network, a light and a look. Then save a PNG or record a 3D orbit or a light sweep.

The app gets Copernicus DEM 30 m elevation and cloud-free Sentinel-2 imagery on Fused with the Fused account
that FusedRender is signed in to. If FusedRender is not signed in, select Sign in on the page. On a phone, sign in on the computer
that runs FusedRender.
The hillshade, colours, 3D view and exports run in the browser, so the controls change the image at once.
On a narrow screen the controls move to a sheet at the bottom. In 3D, drag to orbit and pinch or scroll to zoom.

Requirements: FusedRender signed in to a Fused account, and an internet connection. On the first start FusedRender
installs the Python packages that `pyproject.toml` declares. The Sentinel-2 library is
`sentinel_utils` from fusedio/udfs, pinned to a commit (`PACKAGE_COMMIT` in `tg_common.py`). The first call downloads it
to `.fused/cache/sentinel_utils/`; to use a newer version, change the commit.

Data credit: contains modified Copernicus Sentinel data and Copernicus DEM GLO-30. The map in the area picker uses Esri World Imagery.
