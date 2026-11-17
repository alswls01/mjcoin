# 실행 파일에 넣을 제품 정보(이름, 버전, 만든 곳) 파일을 만든다. 정보가 빈 실행 파일은 백신에 더 의심받음
# 쓰는 법: python version_info.py 1.0.5  → version_info.txt (PyInstaller --version-file 로 넣음)
import sys

v = (sys.argv[1] if len(sys.argv) > 1 else open("web/version.txt", encoding="utf-8").read()).strip().lstrip("v")
n = tuple((int(x) for x in (v.split(".") + ["0"] * 4)[:4]))
open("version_info.txt", "w", encoding="utf-8").write(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={n}, prodvers={n}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('041204B0', [
      StringStruct('CompanyName', 'alswls01'),
      StringStruct('FileDescription', 'MJ코인 시세 보기'),
      StringStruct('FileVersion', '{v}'),
      StringStruct('InternalName', 'MJCoin'),
      StringStruct('LegalCopyright', 'alswls01'),
      StringStruct('OriginalFilename', 'MJCoin.exe'),
      StringStruct('ProductName', 'MJ코인'),
      StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [0x0412, 1200])])
  ]
)
""")
print("version_info.txt", v, n)
