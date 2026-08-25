/* 아트보드 템플릿 렌더러 — 캔버스 편집기 없이 .dc.html 문법을 그대로 돌린다.
 *
 * 지원 범위는 네 아트보드가 실제로 쓰는 것만:
 *   {{ 점표기 }}            텍스트 노드 · 속성값 (전체 또는 문자열 보간)
 *   style="{{ 객체 }}"      renderVals 가 돌려준 스타일 객체
 *   onClick="{{ 함수 }}"    이벤트 핸들러
 *   <template data-for/-as> 반복 (원본 <sc-for list as>)
 *   <template data-if>      분기 (원본 <sc-if value>)
 *   class Component extends DCLogic — state/setState/renderVals/생명주기
 *
 * 렌더는 두 단계다. 먼저 템플릿을 훑어 가벼운 노드 기술(vnode)을 만들고,
 * 그 다음 기존 DOM 을 제자리에서 고친다. 통째로 다시 만들면 안 되는 이유:
 * 재현 영상의 스캔 라인은 1.4초짜리 CSS 애니메이션인데 화면은 0.1초마다 갱신된다.
 * 매번 새 요소로 갈아치우면 애니메이션이 계속 처음으로 되감겨 깨져 보인다.
 * 스크롤 위치·포커스·이미지 디코딩 결과도 같은 이유로 보존된다.
 */
(function (global) {
  "use strict";

  var HOLE = /\{\{\s*([^{}]+?)\s*\}\}/g;
  var WHOLE = /^\s*\{\{\s*([^{}]+?)\s*\}\}\s*$/;
  var own = Object.prototype.hasOwnProperty;

  function lookup(scope, path) {
    if (path === "true") return true;
    if (path === "false") return false;
    if (path === "null") return null;
    var parts = path.split("."), v = scope;
    for (var i = 0; i < parts.length; i++) {
      if (v === null || v === undefined) return undefined;
      v = v[parts[i]];
    }
    return v;
  }

  function interpolate(str, scope) {
    return str.replace(HOLE, function (_, p) {
      var v = lookup(scope, p.trim());
      return v === null || v === undefined ? "" : String(v);
    });
  }

  function wholeHole(str) {
    var m = WHOLE.exec(str);
    return m ? m[1].trim() : null;
  }

  /* ------------------------------------------------ 1단계: 템플릿 -> vnode */

  function compile(node, scope, out) {
    var t = node.nodeType;
    if (t === 3) { out.push({ txt: interpolate(node.nodeValue, scope) }); return; }
    if (t !== 1) return;

    var tag = node.tagName.toLowerCase();

    if (tag === "template" && node.hasAttribute("data-for")) {
      var list = lookup(scope, node.getAttribute("data-for"));
      if (!list || !list.length) return;
      var as = node.getAttribute("data-as") || "item";
      var body = node.content.childNodes;
      for (var i = 0; i < list.length; i++) {
        var inner = Object.create(scope);
        inner[as] = list[i];
        inner.$index = i;
        for (var j = 0; j < body.length; j++) compile(body[j], inner, out);
      }
      return;
    }
    if (tag === "template" && node.hasAttribute("data-if")) {
      if (!lookup(scope, node.getAttribute("data-if"))) return;
      var kids = node.content.childNodes;
      for (var m = 0; m < kids.length; m++) compile(kids[m], scope, out);
      return;
    }

    // 템플릿 DOM 이 이미 올바른 네임스페이스를 들고 있다 (HTML 파서가 <svg> 안을 SVG 로 만든다).
    // 그대로 물려받아 createElementNS 로 만들어야 SVG 가 그려진다.
    var vn = { tag: tag, ns: node.namespaceURI, attrs: {}, style: null, on: null, kids: [] };
    var attrs = node.attributes;
    for (var a = 0; a < attrs.length; a++) {
      var name = attrs[a].name, val = attrs[a].value;
      if (name.indexOf("hint-") === 0) continue;
      var w = wholeHole(val);

      if (name.indexOf("on") === 0 && name.length > 2 && w) {
        var fn = lookup(scope, w);
        if (typeof fn === "function") {
          if (!vn.on) vn.on = {};
          vn.on[name.slice(2).toLowerCase()] = fn;
        }
        continue;
      }
      if (name === "style") {
        vn.style = w ? lookup(scope, w) : interpolate(val, scope);
        continue;
      }
      if (w) {
        var v = lookup(scope, w);
        if (v !== null && v !== undefined && typeof v !== "function" && typeof v !== "object") {
          vn.attrs[name] = String(v);
        }
        continue;
      }
      vn.attrs[name] = interpolate(val, scope);
    }

    var ch = node.childNodes;
    for (var c = 0; c < ch.length; c++) compile(ch[c], scope, vn.kids);
    out.push(vn);
  }

  /* ------------------------------------------------ 2단계: vnode -> DOM */

  function applyStyle(el, val) {
    if (typeof val === "string" || val === null || val === undefined) {
      var s = val || "";
      if (el.__styleStr !== s) { el.setAttribute("style", s); el.__styleStr = s; }
      el.__style = null;
      return;
    }
    el.__styleStr = null;
    var prev = el.__style || {}, next = {}, k;
    // 아트보드 스타일 객체의 길이값은 전부 단위 붙은 문자열이라 그대로 넘기면 된다
    for (k in val) if (own.call(val, k) && val[k] !== null && val[k] !== undefined) next[k] = String(val[k]);
    for (k in prev) {
      if (own.call(next, k)) continue;
      if (k.charAt(0) === "-") el.style.removeProperty(k); else el.style[k] = "";
    }
    for (k in next) {
      if (prev[k] === next[k]) continue;          // 같은 값이면 건드리지 않는다 (애니메이션 유지)
      if (k.charAt(0) === "-") el.style.setProperty(k, next[k]); else el.style[k] = next[k];
    }
    el.__style = next;
  }

  function bind(el, ev) {
    if (!el.__bound) el.__bound = {};
    if (el.__bound[ev]) return;
    el.__bound[ev] = true;
    el.addEventListener(ev, function (e) {
      var h = el.__on && el.__on[ev];
      if (h) h(e);
    });
  }

  function update(el, vn) {
    var prev = el.__attrs || {}, k;
    for (k in prev) if (!own.call(vn.attrs, k)) el.removeAttribute(k);
    for (k in vn.attrs) if (prev[k] !== vn.attrs[k]) el.setAttribute(k, vn.attrs[k]);
    el.__attrs = vn.attrs;

    applyStyle(el, vn.style);

    el.__on = vn.on;
    if (vn.on) for (k in vn.on) bind(el, k);

    patch(el, vn.kids);
  }

  var HTML_NS = "http://www.w3.org/1999/xhtml";

  function create(vn) {
    var el = vn.ns && vn.ns !== HTML_NS
      ? document.createElementNS(vn.ns, vn.tag)
      : document.createElement(vn.tag);
    update(el, vn);
    return el;
  }

  function patch(parent, vnodes) {
    var dom = parent.childNodes, i;
    for (i = 0; i < vnodes.length; i++) {
      var vn = vnodes[i], cur = dom[i];
      if (vn.txt !== undefined) {
        if (cur && cur.nodeType === 3) {
          if (cur.nodeValue !== vn.txt) cur.nodeValue = vn.txt;
        } else {
          var tn = document.createTextNode(vn.txt);
          if (cur) parent.replaceChild(tn, cur); else parent.appendChild(tn);
        }
        continue;
      }
      if (cur && cur.nodeType === 1 && cur.tagName.toLowerCase() === vn.tag
          && cur.namespaceURI === vn.ns) {
        update(cur, vn);
      } else {
        var el = create(vn);
        if (cur) parent.replaceChild(el, cur); else parent.appendChild(el);
      }
    }
    while (dom.length > vnodes.length) parent.removeChild(parent.lastChild);
  }

  /* ------------------------------------------------ 로직 클래스 */

  function DCLogic() {
    this.props = {};
    this.state = {};
  }
  DCLogic.prototype.setState = function (patchObj) {
    var next = typeof patchObj === "function" ? patchObj(this.state) : patchObj;
    var merged = {}, k;
    for (k in this.state) merged[k] = this.state[k];
    for (k in next) merged[k] = next[k];
    this.state = merged;
    this.__schedule();
  };
  DCLogic.prototype.forceUpdate = function () { this.__schedule(); };
  DCLogic.prototype.__schedule = function () {
    var self = this;
    if (!self.__mounted || self.__queued) return;
    self.__queued = true;
    (global.requestAnimationFrame || function (f) { setTimeout(f, 16); })(function () {
      self.__queued = false;
      self.__paint();
    });
  };

  function mount(root, Klass) {
    // 최초 파싱된 DOM 을 템플릿으로 떼어 보관한다 (innerHTML 재파싱은 표 구조를 깨뜨린다)
    var tpl = document.createDocumentFragment();
    while (root.firstChild) tpl.appendChild(root.firstChild);

    var inst = new Klass();
    inst.__paint = function () {
      var vals;
      try { vals = inst.renderVals() || {}; }
      catch (e) { console.error("renderVals 실패", e); return; }
      var vnodes = [];
      for (var i = 0; i < tpl.childNodes.length; i++) compile(tpl.childNodes[i], vals, vnodes);
      patch(root, vnodes);
    };
    inst.__mounted = true;
    inst.__paint();
    if (typeof inst.componentDidMount === "function") inst.componentDidMount();
    global.addEventListener("pagehide", function () {
      if (typeof inst.componentWillUnmount === "function") inst.componentWillUnmount();
    });
    return inst;
  }

  global.DCLogic = DCLogic;
  global.DC = { mount: mount };
})(window);
