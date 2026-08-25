# -*- coding: utf-8 -*-
"""붙임4 끝에 시연 화면 스크린샷을 붙인다 (한글 2010 COM + HWPML).

첨부 자료 목록 뒤에 캡션과 함께 이미지를 이어 넣는다.
"""
import sys, re, io, base64, argparse, shutil, time
import xml.etree.ElementTree as ET
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import win32com.client as win32
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "reports" / "HIMEC AI 활용 아이디어 공모전_출품작.hwp"
SHOTS = ROOT / "reports" / "시연화면"

MM = 7200 / 25.4
PX = 7200 / 96

CAPTIONS = {
    "1_관제화면_지게차협착위험경보.png":
        "① 관제 화면 — 지게차와 작업자의 거리로 판정한 협착 위험(긴급). "
        "각각을 검출하는 것만으로는 나오지 않는 관계 추론 결과라, 관련 객체를 함께 적색으로 표시합니다.",
    "2_현장재현영상_역극셀검출.png":
        "② 현장 재현 영상 — 트레이 1장에서 역극 셀을 셀 단위로 검출. 좌측 카메라 화면, 우측 판독 화면.",
    "3_판독결과_직무별신뢰도와임계값.png":
        "③ 판독 결과 — 6개 직무 · 시험 사진 23장. 항목별 신뢰도 막대에 임계값을 세로선으로 함께 표시합니다.",
    "4_판정작동_클래스별임계값과채택여부.png":
        "④ 판정 작동 — 직무별 검출 클래스와 임계값 설정 근거. 채택/미채택이 그대로 드러납니다.",
    "5_분석리포트_직무별요약.png":
        "⑤ 분석 리포트 — 시험 사진 23장의 판독 결과 요약(검출 채택 131 · 지적 32).",
}


def decode(s):
    return s.encode("utf-16-le").decode("utf-8").rstrip("\x00").rstrip()


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def add_image(xml, path, width_mm, seq):
    im = Image.open(path).convert("RGB")
    buf = io.BytesIO()
    im.save(buf, "JPEG", quality=78, optimize=True)
    raw = buf.getvalue()
    b64 = base64.b64encode(raw).decode()

    cnt = int(re.search(r'<BINDATALIST Count="(\d+)">', xml).group(1))
    nid = cnt + 1
    xml = xml.replace("</BINDATALIST>",
                      f'<BINITEM BinData="{nid}" Format="jpg" Type="Embedding"/></BINDATALIST>', 1)
    xml = xml.replace(f'<BINDATALIST Count="{cnt}">', f'<BINDATALIST Count="{nid}">', 1)
    xml = xml.replace("</BINDATASTORAGE>",
                      f'<BINDATA Encoding="Base64" Id="{nid}" Size="{len(raw)}">{b64}</BINDATA>'
                      "</BINDATASTORAGE>", 1)

    w = int(width_mm * MM)
    h = int(w * im.size[1] / im.size[0])
    ow, oh = int(im.size[0] * PX), int(im.size[1] * PX)
    pic = (
        f'<PICTURE Reverse="false"><SHAPEOBJECT InstId="20{seq}0{nid}1" Lock="false" '
        f'NumberingType="Figure" ZOrder="{20+seq}"><SIZE Height="{h}" HeightRelTo="Absolute" '
        f'Protect="false" Width="{w}" WidthRelTo="Absolute"/><POSITION AffectLSpacing="false" '
        f'AllowOverlap="false" FlowWithText="true" HoldAnchorAndSO="false" HorzAlign="Left" '
        f'HorzOffset="0" HorzRelTo="Column" TreatAsChar="true" VertAlign="Top" VertOffset="0" '
        f'VertRelTo="Para"/><OUTSIDEMARGIN Bottom="0" Left="0" Right="0" Top="0"/></SHAPEOBJECT>'
        f'<SHAPECOMPONENT CurHeight="{h}" CurWidth="{w}" GroupLevel="0" HorzFlip="false" '
        f'InstID="21{seq}0{nid}2" OriHeight="{oh}" OriWidth="{ow}" VertFlip="false" XPos="0" YPos="0">'
        f'<ROTATIONINFO Angle="0" CenterX="{w//2}" CenterY="{h//2}"/><RENDERINGINFO>'
        f'<TRANSMATRIX E1="1.00000" E2="0.00000" E3="0.00000" E4="0.00000" E5="1.00000" E6="0.00000"/>'
        f'<SCAMATRIX E1="{w/ow:.5f}" E2="0.00000" E3="0.00000" E4="0.00000" E5="{h/oh:.5f}" E6="0.00000"/>'
        f'<ROTMATRIX E1="1.00000" E2="0.00000" E3="0.00000" E4="0.00000" E5="1.00000" E6="0.00000"/>'
        f'</RENDERINGINFO></SHAPECOMPONENT>'
        f'<IMAGERECT X0="0" X1="{ow}" X2="{ow}" X3="0" Y0="0" Y1="0" Y2="{oh}" Y3="{oh}"/>'
        f'<IMAGECLIP Bottom="{oh}" Left="0" Right="{ow}" Top="0"/>'
        f'<INSIDEMARGIN Bottom="0" Left="0" Right="0" Top="0"/>'
        f'<IMAGE Alpha="0" BinItem="{nid}" Bright="0" Contrast="0" Effect="RealPic"/>'
        f'<EFFECTS/></PICTURE>')
    return xml, pic, len(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width-mm", type=float, default=150)
    a = ap.parse_args()

    hwp = win32.Dispatch("HWPFrame.HwpObject")
    hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
    assert hwp.Open(str(DOC), "HWP", "forceopen:true"), "문서 열기 실패"
    xml = decode(hwp.GetTextFile("HWPML2X", ""))
    print(f"HWPML 로드 {len(xml):,}자\n")

    # 삽입 위치는 이미지 등록이 끝난 뒤에 잡는다.
    # add_image 가 문서 앞쪽 BINDATALIST 를 늘리므로, 미리 구한 오프셋은 그만큼 밀린다.
    tail = "README : 프로젝트 구조 및 재현 실행 방법"
    ps = re.search(r'<P ParaShape="(\d+)" Style="0"><TEXT CharShape="(\d+)"><CHAR>· ' + tail, xml)
    pshape, cshape = (ps.group(1), ps.group(2)) if ps else ("38", "83")

    blocks = [f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}"><CHAR> </CHAR></TEXT></P>',
              f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}">'
              f'<CHAR>[시연 화면]</CHAR></TEXT></P>',
              # 새 쪽 맨 위가 머리말 띠와 겹치므로 공백 문단으로 내려 준다
              f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}"><CHAR> </CHAR></TEXT></P>',
              f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}"><CHAR> </CHAR></TEXT></P>']
    total = 0
    for seq, name in enumerate(sorted(CAPTIONS), 1):
        path = SHOTS / name
        if not path.exists():
            print(f"  -- {name} 없음 (건너뜀)")
            continue
        xml, pic, size = add_image(xml, path, a.width_mm, seq)
        total += size
        # 서명 삽입에서 통했던 구조를 그대로 쓴다 — PICTURE 를 CHAR 사이에 둔다
        blocks.append(f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}">'
                      f'<CHAR> </CHAR>{pic}<CHAR> </CHAR></TEXT></P>')
        blocks.append(f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}">'
                      f'<CHAR>{esc(CAPTIONS[name])}</CHAR></TEXT></P>')
        blocks.append(f'<P ParaShape="{pshape}" Style="0"><TEXT CharShape="{cshape}"><CHAR> </CHAR></TEXT></P>')
        print(f"  ok  {name}  ({size//1024} KB)")

    i = xml.index(tail)
    end = xml.index("</P>", i) + 4
    xml = xml[:end] + "".join(blocks) + xml[end:]
    print(f"\n이미지 {len(blocks)//3}장 · {total/1e6:.1f} MB")

    try:
        ET.fromstring(xml.encode("utf-8"))
        print("XML 적합성: 통과")
    except ET.ParseError as e:
        raise SystemExit(f"XML 오류 — 저장 중단: {e}")

    hml = DOC.with_suffix(".hml")
    hml.write_text(xml, encoding="utf-8")
    hwp.Clear(1)
    assert hwp.Open(str(hml), "HWPML2X", "forceopen:true"), "HWPML 열기 실패"
    tmp = DOC.with_name("_shots.hwp")
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
    print("저장:", DOC)


if __name__ == "__main__":
    main()
