# -*- coding: utf-8 -*-
"""붙임1~3 의 신청자 정보와 서명을 채운다 (한글 2010 COM + HWPML).

make_submission_hwp.py 가 만든 문서 위에 신청자 개인정보를 얹는다.

주민등록번호는 이 스크립트가 채우지 않는다.
고유식별정보라 자동 입력 대상에서 제외했고, 한글에서 본인이 직접 기입해야 한다.
(붙임3 「수집하는 개인정보 항목」 칸은 양식 안내문이고, 실제 기입란은 따로 없다.)
"""
import sys, re, io, base64, argparse
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import win32com.client as win32
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "reports" / "HIMEC AI 활용 아이디어 공모전_출품작.hwp"

MM = 7200 / 25.4          # 1mm 당 HWPUNIT
PX = 7200 / 96            # 1px 당 HWPUNIT (한글은 96dpi 기준)


def decode(s):
    return s.encode("utf-16-le").decode("utf-8").rstrip("\x00").rstrip()


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def sub1(xml, old, new, label):
    if xml.count(old) != 1:
        raise SystemExit(f"[{label}] 앵커 {xml.count(old)}개 (1개여야 함)")
    print(f"  ok  {label}")
    return xml.replace(old, new)


def add_image(xml, path, width_mm):
    """서명 그림을 BINDATA 로 추가하고, 삽입에 쓸 PICTURE 조각을 돌려준다."""
    im = Image.open(path).convert("RGBA")
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode()

    cnt = int(re.search(r'<BINDATALIST Count="(\d+)">', xml).group(1))
    new_id = cnt + 1
    xml = xml.replace("</BINDATALIST>",
                      f'<BINITEM BinData="{new_id}" Format="png" Type="Embedding"/></BINDATALIST>', 1)
    xml = xml.replace(f'<BINDATALIST Count="{cnt}">', f'<BINDATALIST Count="{new_id}">', 1)
    xml = xml.replace("</BINDATASTORAGE>",
                      f'<BINDATA Encoding="Base64" Id="{new_id}" Size="{len(raw)}">{b64}</BINDATA>'
                      "</BINDATASTORAGE>", 1)

    w = int(width_mm * MM)
    h = int(w * im.size[1] / im.size[0])
    ow, oh = int(im.size[0] * PX), int(im.size[1] * PX)
    pic = (
        f'<PICTURE Reverse="false"><SHAPEOBJECT InstId="1900{new_id}01" Lock="false" '
        f'NumberingType="Figure" ZOrder="9"><SIZE Height="{h}" HeightRelTo="Absolute" '
        f'Protect="false" Width="{w}" WidthRelTo="Absolute"/><POSITION AffectLSpacing="false" '
        f'AllowOverlap="false" FlowWithText="true" HoldAnchorAndSO="false" HorzAlign="Left" '
        f'HorzOffset="0" HorzRelTo="Column" TreatAsChar="true" VertAlign="Top" VertOffset="0" '
        f'VertRelTo="Para"/><OUTSIDEMARGIN Bottom="0" Left="0" Right="0" Top="0"/></SHAPEOBJECT>'
        f'<SHAPECOMPONENT CurHeight="{h}" CurWidth="{w}" GroupLevel="0" HorzFlip="false" '
        f'InstID="1901{new_id}02" OriHeight="{oh}" OriWidth="{ow}" VertFlip="false" XPos="0" YPos="0">'
        f'<ROTATIONINFO Angle="0" CenterX="{w//2}" CenterY="{h//2}"/><RENDERINGINFO>'
        f'<TRANSMATRIX E1="1.00000" E2="0.00000" E3="0.00000" E4="0.00000" E5="1.00000" E6="0.00000"/>'
        f'<SCAMATRIX E1="{w/ow:.5f}" E2="0.00000" E3="0.00000" E4="0.00000" E5="{h/oh:.5f}" E6="0.00000"/>'
        f'<ROTMATRIX E1="1.00000" E2="0.00000" E3="0.00000" E4="0.00000" E5="1.00000" E6="0.00000"/>'
        f'</RENDERINGINFO></SHAPECOMPONENT>'
        f'<IMAGERECT X0="0" X1="{ow}" X2="{ow}" X3="0" Y0="0" Y1="0" Y2="{oh}" Y3="{oh}"/>'
        f'<IMAGECLIP Bottom="{oh}" Left="0" Right="{ow}" Top="0"/>'
        f'<INSIDEMARGIN Bottom="0" Left="0" Right="0" Top="0"/>'
        f'<IMAGE Alpha="0" BinItem="{new_id}" Bright="0" Contrast="0" Effect="RealPic"/>'
        f'<EFFECTS/></PICTURE>')
    print(f"  ok  서명 그림 등록 (BinItem={new_id}, {im.size[0]}x{im.size[1]}px -> {width_mm}mm)")
    return xml, pic


def sign_after(xml, anchor_text, pic, name, label):
    """anchor 뒤 첫 '(인)' 자리에 성명과 서명을 넣는다."""
    i = xml.index(f"<CHAR>{anchor_text}</CHAR>")
    m = re.compile(r"<CHAR>\(인\)</CHAR>").search(xml, i)
    if not m:
        raise SystemExit(f"[{label}] (인) 을 찾지 못함")
    rep = f"<CHAR>{esc(name)}   </CHAR>{pic}"
    print(f"  ok  {label}")
    return xml[:m.start()] + rep + xml[m.end():]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True)
    ap.add_argument("--phone", required=True)
    ap.add_argument("--org", required=True)
    ap.add_argument("--dept", required=True)
    ap.add_argument("--sign", required=True, help="서명 이미지 파일")
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--agree", action="store_true", help="붙임3 개인정보 수집·이용 동의 체크")
    a = ap.parse_args()
    y, mth, d = a.date.split("-")

    hwp = win32.Dispatch("HWPFrame.HwpObject")
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    assert hwp.Open(str(DOC), "HWP", "forceopen:true"), "문서 열기 실패"
    xml = decode(hwp.GetTextFile("HWPML2X", ""))
    print(f"HWPML 로드 {len(xml):,}자\n")

    xml, pic = add_image(xml, a.sign, width_mm=14)

    print("\n[붙임1 참가신청서]")
    # E-Mail 값 칸이 쓰는 서식을 그대로 빌려 쓴다 (안내문 서식은 회색·작은 글씨라 부적절)
    vshape = re.search(r'<CHAR>E-Mail</CHAR></TEXT></P></PARALIST></CELL>'
                       r'.*?<TEXT CharShape="(\d+)">', xml, re.S).group(1)
    xml = sub1(xml, '<TEXT CharShape="54"><CHAR> ※‘팀’은 팀명, ‘기업’은 대표이사명 기재</CHAR></TEXT>',
               f'<TEXT CharShape="{vshape}"><CHAR>{esc(a.name)}</CHAR></TEXT>', "신청자명")
    # 연락처 값 칸은 비어 있다 — '연 락 처' 라벨 셀 다음 셀의 빈 TEXT 를 채운다
    i = xml.index("<CHAR>연 락 처</CHAR>")
    j = xml.index("</CELL>", i)
    m = re.compile(r'<TEXT CharShape="(\d+)"/>').search(xml, j)
    xml = xml[:m.start()] + f'<TEXT CharShape="{m.group(1)}"><CHAR>{esc(a.phone)}</CHAR></TEXT>' + xml[m.end():]
    print("  ok  연락처")
    xml = sub1(xml, "<CHAR>직장(학교) : </CHAR>",
               f"<CHAR>직장(학교) : {esc(a.org)}</CHAR>", "소속 직장")
    xml = sub1(xml, "<CHAR>※일반인의 경우, 소속 학교 및 직장이 없으면 ‘해당사항 없음’ 기재</CHAR>",
               "<CHAR></CHAR>", "소속 안내문구 제거")
    xml = sub1(xml, "<CHAR>부서(학과) : </CHAR>",
               f"<CHAR>부서(학과) : {esc(a.dept)}</CHAR>", "소속 부서")

    # 날짜 — 붙임1·2·3 세 곳
    n = 0
    for pat in [r"<CHAR>(\s*)년(\s+)월(\s+)일(\s*)</CHAR>"]:
        xml, k = re.subn(pat, f"<CHAR>  {y} 년  {int(mth)} 월  {int(d)} 일  </CHAR>", xml)
        n += k
    print(f"  ok  날짜 {n}곳")

    print("\n[서명]")
    # 붙임1 신청인 줄은 '신청인(대표자) ... (인)' 이 한 CHAR 안에 있다
    m = re.search(r"<CHAR>([^<]*신청인\(대표자\)[^<]*)</CHAR>", xml)
    if m:
        head = m.group(1).split("(인)")[0].rstrip() + "  "
        xml = xml[:m.start()] + f"<CHAR>{esc(head)}</CHAR>{pic}" + xml[m.end():]
        print("  ok  붙임1 신청인 서명")
    xml = sign_after(xml, "개 인", pic, a.name, "붙임2 개인 서명")
    # 붙임3 의 '개 인' 은 두 번째 등장
    i2 = xml.index("<CHAR>개 인</CHAR>", xml.index("<CHAR>개 인</CHAR>") + 1)
    m = re.compile(r"<CHAR>\(인\)</CHAR>").search(xml, i2)
    xml = (xml[:m.start()] + f"<CHAR>{esc(a.name)}   </CHAR>{pic}" + xml[m.end():])
    print("  ok  붙임3 개인 서명")

    if a.agree:
        print("\n[붙임3 동의]")
        xml, k = re.subn(r"□(\s*)동의합니다\.", r"■\1동의합니다.", xml)
        print(f"  ok  동의 체크 {k}곳  (동의하지 않습니다 는 그대로 둠)")

    try:
        ET.fromstring(xml.encode("utf-8"))
        print("\nXML 적합성: 통과")
    except ET.ParseError as e:
        raise SystemExit(f"XML 오류 — 저장 중단: {e}")

    hml = DOC.with_suffix(".hml")
    hml.write_text(xml, encoding="utf-8")
    hwp.Clear(1)
    assert hwp.Open(str(hml), "HWPML2X", "forceopen:true"), "HWPML 열기 실패"
    # 원본과 같은 경로로 바로 저장하면 한글이 잡고 있는 핸들과 충돌한다
    tmp = DOC.with_name("_filled.hwp")
    assert hwp.SaveAs(str(tmp), "HWP", ""), "저장 실패"
    hwp.Clear(1)
    hwp.Quit()
    hml.unlink()
    # 한글이 원본 핸들을 놓을 때까지 잠깐 기다렸다 교체한다
    import shutil, time
    for _ in range(15):
        try:
            shutil.move(str(tmp), str(DOC))
            break
        except PermissionError:
            time.sleep(1)
    else:
        raise SystemExit(f"원본 교체 실패 — {tmp} 를 직접 옮기세요")
    print("저장:", DOC)
    print("\n※ 주민등록번호는 채우지 않았습니다. 한글에서 직접 기입하세요.")


if __name__ == "__main__":
    main()
