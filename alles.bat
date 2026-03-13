@echo off
del alles_py.txt 2>nul

for /r %%f in (*.py) do (
  echo ===== %%f =====>>alles_py.txt
  type "%%f">>alles_py.txt
  echo.>>alles_py.txt
)
