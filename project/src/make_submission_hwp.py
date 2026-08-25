# -*- coding: utf-8 -*-
"""공모전 제출서류 HWP 양식을 직접 채운다 (한글 2010 COM + HWPML).

방식
  1. 원본 .hwp 를 열어 HWPML(XML)로 받는다.
     COM 은 UTF-8 바이트열을 UTF-16LE 로 잘못 디코딩한 str 을 주므로 되돌린다.
  2. XML 을 문자열 수준에서 최소 침습으로 고친다 (표 셀의 PARALIST 만 교체).
  3. 다시 넣고 .hwp 로 저장한다.

채우지 않는 것 — 개인정보이므로 본인이 직접 작성해야 한다.
  신청자명 · 연락처 · 소속 · 팀원 · 생년월일 · 주민등록번호 · 서명(인) · 날짜
  붙임2 참가서약서, 붙임3 개인정보 동의서 전체
"""
import os, sys, re, json, importlib.util
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
import win32com.client as win32

ROOT = Path(r"C:\Users\samkoo\Desktop\himec\project")
SRC = (r"C:\Users\samkoo\Desktop\himec\제1회 HIMEC AI 활용 아이디어 공모전"
       r"\제1회 HIMEC AI 활용 아이디어 공모전"
       r"\2. 붙임+제출서류(제1회 HIMEC AI 활용 아이디어 공모전).hwp")
OUT_HWP = ROOT / "reports" / "HIMEC AI 활용 아이디어 공모전_출품작.hwp"

APPLICANT_EMAIL = os.environ.get("APPLICANT_EMAIL", "")

# ── 붙임4 본문은 docx 생성기의 상수를 그대로 쓴다 (한 곳에서만 관리) ──────
spec = importlib.util.spec_from_file_location("mk", ROOT / "src" / "make_submission_docx.py")
mk = importlib.util.module_from_spec(spec)
sys.argv = ["x"]
try:
    spec.loader.exec_module(mk)
except SystemExit:
    pass

perf_txt = mk.build_perf(ROOT / "reports" / "performance.json")

PROPOSAL = mk.PROPOSAL.replace("{PERF}", perf_txt)


# ── XML 조작 도구 ────────────────────────────────────────────────────
def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def build_paras(text, para_shape, char_shape):
    out = []
    for line in text.split("\n"):
        if line.strip():
            out.append(f'<P ParaShape="{para_shape}" Style="0">'
                       f'<TEXT CharShape="{char_shape}"><CHAR>{esc(line)}</CHAR></TEXT></P>')
        else:
            out.append(f'<P ParaShape="{para_shape}" Style="0">'
                       f'<TEXT CharShape="{char_shape}"/></P>')
    return "".join(out)


def shapes_in(frag, fallback=("39", "37")):
    p = re.search(r'<P ParaShape="(\d+)"', frag)
    c = re.search(r'<TEXT CharShape="(\d+)"', frag)
    return (p.group(1) if p else fallback[0], c.group(1) if c else fallback[1])


def replace_paralist(xml, start, text, label, char_shape=None):
    """start 위치를 포함하는 PARALIST 의 내용을 text 로 갈아끼운다."""
    a = xml.rfind("<PARALIST", 0, start)
    open_end = xml.index(">", a) + 1
    b = xml.index("</PARALIST>", start)
    ps, cs = shapes_in(xml[open_end:b])
    cs = char_shape or cs
    new = build_paras(text, ps, cs)
    print(f"  ok  {label}  (ParaShape={ps} CharShape={cs}, {len(text)}자)")
    return xml[:open_end] + new + xml[b:]


def fill_cell_containing(xml, marker, text, label, char_shape=None):
    i = xml.index(marker)
    return replace_paralist(xml, i, text, label, char_shape)


def fill_cell_after_label(xml, label_text, text, label):
    """라벨 셀 바로 다음 셀을 채운다 (빈 칸을 채울 때)."""
    i = xml.index(f"<CHAR>{label_text}</CHAR>")
    j = xml.index("</CELL>", i)
    k = xml.index("<PARALIST", j)
    return replace_paralist(xml, k + 10, text, label)


def tick(xml, item, label):
    """'□ item' 을 '■ item' 으로. 체크박스와 항목이 다른 TEXT 런에 나뉘어 있다."""
    pat = re.compile(r"□ (</CHAR></TEXT><TEXT CharShape=\"\d+\"><CHAR>)" + re.escape(item))
    xml, n = pat.subn(r"■ \1" + item, xml)
    if n == 0:                                  # 한 런 안에 같이 있는 경우
        xml, n = re.subn("□ " + re.escape(item), "■ " + item, xml)
    print(f"  ok  {label}  ({n}곳)")
    return xml


# ── 본 작업 ──────────────────────────────────────────────────────────
def decode(s):
    # COM 문자열 끝에 종단용 NUL 이 딸려 온다. 한글은 무시하지만 XML 파서는 오류를 낸다.
    return s.encode("utf-16-le").decode("utf-8").rstrip("\x00").rstrip()


def encode(x):
    return x.encode("utf-8").decode("utf-16-le")


hwp = win32.Dispatch("HWPFrame.HwpObject")
hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModule")
assert hwp.Open(SRC, "HWP", "forceopen:true"), "원본 양식 열기 실패"
xml = decode(hwp.GetTextFile("HWPML2X", ""))
print(f"HWPML 로드 {len(xml):,}자\n")

def add_black_charshape(xml, clone_of="72"):
    """예시문 서식(회색 #B2B2B2)을 복제해 글자색만 검정으로 바꾼 서식을 추가한다.

    붙임4 설명 칸의 예시문은 회색이라, 그 서식을 그대로 물려받으면
    제출 본문까지 회색으로 인쇄된다.
    """
    m = re.search(r'<CHARSHAPE [^>]*Id="' + clone_of + r'"[^>]*>.*?</CHARSHAPE>', xml, re.S)
    if not m:
        raise SystemExit(f"CHARSHAPE {clone_of} 없음")
    cnt = int(re.search(r'<CHARSHAPELIST Count="(\d+)">', xml).group(1))
    new_id = str(max(int(i) for i in re.findall(r'<CHARSHAPE [^>]*Id="(\d+)"', xml)) + 1)
    clone = (m.group(0)
             .replace(f'Id="{clone_of}"', f'Id="{new_id}"', 1)
             .replace('TextColor="11711154"', 'TextColor="0"', 1))
    xml = xml.replace("</CHARSHAPELIST>", clone + "</CHARSHAPELIST>", 1)
    xml = xml.replace(f'<CHARSHAPELIST Count="{cnt}">',
                      f'<CHARSHAPELIST Count="{cnt + 1}">', 1)
    print(f"  ok  검정 글자 서식 추가 (Id={new_id}, {clone_of} 복제)")
    return xml, new_id


def relax_row_height(xml, marker, label, height="2000"):
    """마커가 든 행의 셀 높이를 줄여 한글이 내용에 맞게 다시 계산하게 한다.

    양식에 저장된 높이를 그대로 두면 본문이 길어져도 칸이 커지지 않아
    글자가 칸 밖으로 넘치고 바닥글까지 침범한다.
    """
    i = xml.index(marker)
    a = xml.rindex("<ROW>", 0, i)
    b = xml.index("</ROW>", i) + 6
    row = xml[a:b]
    row2, n = re.subn(r'(<CELL [^>]*?)Height="\d+"', r'\1Height="' + height + '"', row)
    print(f"  ok  {label} 행 높이 재계산 ({n}개 셀)")
    return xml[:a] + row2 + xml[b:]


print("[서식]")
xml, BLACK = add_black_charshape(xml)

print("\n[붙임1 참가신청서]")
xml = tick(xml, "시공·품질관리", "공모분야 ■ 시공·품질관리")
xml = tick(xml, "개인", "지원형태 ■ 개인")
xml = fill_cell_after_label(xml, "출품작 명칭", mk.TITLE, "출품작 명칭")
xml = fill_cell_after_label(xml, "E-Mail", APPLICANT_EMAIL, "E-Mail")
xml = fill_cell_containing(xml, "* 출품작의 내용을 함축적으로 설명", mk.SUMMARY, "공모 내용/요약")

print("\n[붙임4 출품작]")
M1 = "- 현황, 문제점 및 개선 필요 사항 등"
M2 = "- 현재 해결하고자 하는 문제를 구체적으로 작성"
xml = relax_row_height(xml, M1, "(1) 제안 배경")
xml = relax_row_height(xml, M2, "(2) 제안 내용")
xml = fill_cell_containing(xml, M1, mk.BACKGROUND, "(1) 제안 배경 및 분야", char_shape=BLACK)
xml = fill_cell_containing(xml, M2, PROPOSAL, "(2) 제안 내용", char_shape=BLACK)

# 붙임4 첫머리 '1. 출품작 명칭 :' 과 '(3) 첨부 자료' 는 표 밖 문단이다
i = xml.find("<CHAR>1. 출품작 명칭 : </CHAR>")
if i < 0:
    i = xml.find("1. 출품작 명칭")
if i >= 0:
    j = xml.index("</CHAR>", i)
    head = xml[xml.rindex("<CHAR>", 0, j):j] + "</CHAR>"
    xml = xml[:xml.rindex("<CHAR>", 0, j)] + f"<CHAR>1. 출품작 명칭 : {esc(mk.TITLE)}</CHAR>" + xml[j + 7:]
    print("  ok  1. 출품작 명칭")

def append_after_paragraph(xml, marker, text, label):
    """마커가 든 문단 '뒤에' 새 문단들을 이어 붙인다.

    이 문단은 안에 그림(HEADER>PARALIST>P)이 중첩돼 있어 통째로 바꾸면
    닫는 태그를 먹는다. 마커 뒤의 첫 </P> 는 바깥 문단의 것이므로 거기에 붙인다.
    """
    i = xml.index(marker)
    end = xml.index("</P>", i) + 4
    ps = re.search(r'<P ParaShape="(\d+)" Style="0"><TEXT CharShape="\d+"><CHAR>\(3\) 첨부 자료',
                   xml)
    cs = re.search(r'<TEXT CharShape="(\d+)"><CHAR>' + re.escape(marker), xml)
    ps = ps.group(1) if ps else "63"
    cs = cs.group(1) if cs else "83"
    print(f"  ok  {label}  (ParaShape={ps} CharShape={cs}, {len(text)}자)")
    return xml[:end] + build_paras(text, ps, cs) + xml[end:]


def pad_before_heading(xml, heading, lines_n, label):
    """제목 문단 앞에 빈 줄을 넣어 머리말(로고·괘선)과 겹치지 않게 내린다.

    본문이 길어지면서 이 제목이 새 쪽 맨 위로 밀리는데, 그 자리는 머리말이
    그려지는 띠라 글자가 로고 위에 겹쳐 인쇄된다.
    """
    m = re.search(r'<P ParaShape="(\d+)" Style="0"><TEXT CharShape="(\d+)"><CHAR>'
                  + re.escape(heading), xml)
    if not m:
        print(f"  -- {label} 제목 못 찾음 (건너뜀)")
        return xml
    # 완전히 빈 문단은 쪽 맨 위에서 무시된다. 공백 한 칸을 넣어야 실제로 자리를 차지한다.
    blank = (f'<P ParaShape="{m.group(1)}" Style="0">'
             f'<TEXT CharShape="{m.group(2)}"><CHAR> </CHAR></TEXT></P>')
    print(f"  ok  {label} 앞 빈 줄 {lines_n}개")
    return xml[:m.start()] + blank * lines_n + xml[m.start():]


xml = pad_before_heading(xml, "(3) 첨부 자료", 2, "(3) 첨부 자료")
xml = append_after_paragraph(xml, "PPT, 프로토타입, GitHub주소", mk.ATTACH, "(3) 첨부 자료")

print(f"\nHWPML 수정 완료 {len(xml):,}자")

# 태그 균형이 깨지면 한글이 파일을 아예 못 연다 — 저장 전에 잡는다
import xml.etree.ElementTree as ET  # noqa: E402
try:
    ET.fromstring(xml.encode("utf-8"))
    print("XML 적합성: 통과")
except ET.ParseError as e:
    dbg = Path(r"C:\Users\samkoo\AppData\Local\Temp\fail.hml")
    dbg.write_text(xml, encoding="utf-8")
    line, col = e.position
    seg = xml.split("\n")[line - 1] if line - 1 < len(xml.split("\n")) else ""
    print("문제 지점:", repr(seg[max(0, col - 120):col + 120]))
    raise SystemExit(f"XML 오류 — 저장 중단: {e}  (덤프: {dbg})")

# SetTextFile 로 문자열을 되돌리는 길은 쓰지 않는다.
# COM 이 UTF-8 바이트를 UTF-16 문자열로 넘기는 탓에, 바이트 수가 홀수면 되돌릴 수 없고
# 짝수여도 조용히 어긋난 채 원본이 그대로 저장된다. .hml 파일로 내보내 한글이 직접 열게 한다.
HML = OUT_HWP.with_suffix(".hml")
HML.write_text(xml, encoding="utf-8")
print(f"HWPML 파일: {HML.name} ({HML.stat().st_size:,} bytes)")

hwp.Clear(1)
assert hwp.Open(str(HML), "HWPML2X", "forceopen:true"), "HWPML 열기 실패"
assert hwp.SaveAs(str(OUT_HWP), "HWP", ""), "SaveAs 실패"
hwp.Clear(1)
hwp.Quit()
HML.unlink()
print("저장:", OUT_HWP)
