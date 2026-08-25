# -*- coding: utf-8 -*-
"""유튜브 시연영상 링크를 붙임4에 반영하고 제출 ZIP까지 다시 만든다.

  python src/add_youtube.py --url https://youtu.be/XXXXXXXXXXX --team 홍길동

여러 번 실행해도 된다. 이미 들어간 링크는 새 링크로 교체된다.
"""
import sys, re, argparse, shutil, time, subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import win32com.client as win32

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "reports" / "HIMEC AI 활용 아이디어 공모전_출품작.hwp"
TAILNOTE = "← 관제 화면 36초 (4개 현장 · 판독부터 경보 확정까지)"


def decode(s):
    return s.encode("utf-16-le").decode("utf-8").rstrip("\x00").rstrip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--team", required=True, help="ZIP 파일명에 들어갈 이름")
    ap.add_argument("--no-zip", action="store_true")
    a = ap.parse_args()

    if not re.match(r"https?://(youtu\.be/|(www\.)?youtube\.com/)", a.url):
        raise SystemExit(f"유튜브 주소로 보이지 않습니다: {a.url}")

    hwp = win32.Dispatch("HWPFrame.HwpObject")
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    assert hwp.Open(str(DOC), "HWP", "forceopen:true"), "문서 열기 실패"
    xml = decode(hwp.GetTextFile("HWPML2X", ""))

    # 자리표시자든 이전 링크든 한 줄을 통째로 갈아끼운다
    pat = re.compile(r"<CHAR>(\s*)https?://(?:youtu\.be/|(?:www\.)?youtube\.com/)[^<]*</CHAR>")
    m = pat.search(xml)
    if not m:
        hwp.Clear(1); hwp.Quit()
        raise SystemExit("붙임4 에서 시연 영상 줄을 찾지 못했습니다")
    xml = xml[:m.start()] + f"<CHAR>{m.group(1)}{a.url}          {TAILNOTE}</CHAR>" + xml[m.end():]
    print(f"  ok  시연 영상 링크 -> {a.url}")

    try:
        ET.fromstring(xml.encode("utf-8"))
    except ET.ParseError as e:
        raise SystemExit(f"XML 오류 — 저장 중단: {e}")

    hml = DOC.with_suffix(".hml")
    hml.write_text(xml, encoding="utf-8")
    hwp.Clear(1)
    assert hwp.Open(str(hml), "HWPML2X", "forceopen:true"), "HWPML 열기 실패"
    tmp = DOC.with_name("_yt.hwp")
    assert hwp.SaveAs(str(tmp), "HWP", ""), "저장 실패"
    hwp.Clear(1)
    hwp.Quit()
    hml.unlink()
    for _ in range(15):
        try:
            shutil.move(str(tmp), str(DOC))
            break
        except PermissionError:
            time.sleep(1)
    else:
        raise SystemExit(f"원본 교체 실패 — {tmp} 를 직접 옮기세요")
    print("저장:", DOC.name)

    if not a.no_zip:
        old = ROOT / "reports" / f"HIMEC AI 활용 아이디어 공모전_{a.team}.zip"
        old.unlink(missing_ok=True)
        subprocess.run([sys.executable, str(ROOT / "src" / "make_package.py"),
                        "--team", a.team], check=True)


if __name__ == "__main__":
    main()
