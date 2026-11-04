/*
 * Fernway support widget loader. Add to any page:
 *   <script src="https://YOUR-HOST/embed.js" defer></script>
 * The widget runs in an iframe, so it cannot clash with the host page's CSS or JS.
 */
(function () {
  if (window.__fernwayWidget) return;
  window.__fernwayWidget = true;
  var origin = new URL(document.currentScript.src).origin;
  var open = false;

  var frame = document.createElement("iframe");
  frame.src = origin + "/widget";
  frame.title = "Customer support chat";
  frame.style.cssText =
    "position:fixed;bottom:96px;right:24px;width:390px;height:620px;max-width:calc(100vw - 32px);" +
    "max-height:calc(100vh - 120px);border:0;border-radius:16px;box-shadow:0 20px 50px rgba(0,0,0,.2);" +
    "z-index:2147483646;display:none;background:#fff";

  var button = document.createElement("button");
  button.setAttribute("aria-label", "Open support chat");
  button.innerHTML =
    '<svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/></svg>';
  button.style.cssText =
    "position:fixed;bottom:24px;right:24px;width:56px;height:56px;border-radius:50%;border:0;cursor:pointer;" +
    "background:#166534;box-shadow:0 10px 25px rgba(0,0,0,.25);z-index:2147483647;display:flex;align-items:center;justify-content:center";
  button.onclick = function () {
    open = !open;
    frame.style.display = open ? "block" : "none";
    button.setAttribute("aria-label", open ? "Close support chat" : "Open support chat");
  };

  document.body.appendChild(frame);
  document.body.appendChild(button);
})();
