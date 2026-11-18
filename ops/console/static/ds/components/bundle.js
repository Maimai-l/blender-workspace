/* Endfield 控件脚本：纯 JavaScript，无依赖。
   window.Endfield.init(root) 挂载图标雪碧图并为 root 内的控件绑定交互；可重复调用，已绑定的元素会跳过。
   window.Endfield.icons 为全部图标（id: [viewBox, 内容]），用法：<svg class="ic"><use href="#i-check"/></svg>。 */
(function(){
var ICONS={"i-chev-l": ["0 0 18 27", "<path d=\"M14.142,0.127 L17.753,3.737 L7.963,13.527 L17.753,23.318 L14.142,26.928 L0.743,13.527 L14.142,0.127 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-chev-r": ["0 0 18 27", "<path transform=\"matrix(-1 0 0 1 18 0)\" d=\"M14.142,0.127 L17.753,3.737 L7.963,13.527 L17.753,23.318 L14.142,26.928 L0.743,13.527 L14.142,0.127 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-chev-d": ["0 -4.5 27 27", "<path transform=\"rotate(-90 13.5 13.5) translate(4.5 0)\" d=\"M14.142,0.127 L17.753,3.737 L7.963,13.527 L17.753,23.318 L14.142,26.928 L0.743,13.527 L14.142,0.127 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-tri-d": ["0 0 16 16", "<path d=\"M4 6h8l-4 5z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-check": ["0 0 16 16", "<path d=\"M7.14,13.13 L14.83,5.45 A1.23,1.23 0 0 0 14.83,3.71 A1.23,1.23 0 0 0 13.08,3.71 L5.4,11.39 A1.23,1.23 0 0 0 5.4,13.13 A1.23,1.23 0 0 0 7.14,13.13 Z M1.29,8.43 L3.36,10.41 A1.23,1.23 0 0 0 5.11,10.36 A1.23,1.23 0 0 0 5.06,8.62 L2.98,6.65 A1.23,1.23 0 0 0 1.24,6.69 A1.23,1.23 0 0 0 1.29,8.43 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-minus": ["0 0 16 16", "<path d=\"M4 8h8\"/>"], "i-close": ["0 0 57 57", "<path fill-rule=\"evenodd\" d=\"M28.137,20.301 L48.026,0.414 L55.651,8.038 L35.762,27.925 L28.137,20.301 ZM56.625,48.787 L49.000,56.411 L28.137,35.550 L35.762,27.925 L56.625,48.787 ZM8.428,55.256 L0.803,47.632 L20.511,27.925 L28.137,35.550 L8.428,55.256 ZM1.777,9.193 L9.402,1.568 L28.137,20.301 L20.511,27.925 L1.777,9.193 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-arrow-r": ["-3.13 -3.92 31 31", "<path transform=\"rotate(-45 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-arrow-dr": ["-0.48 -0.36 24 24", "<path d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-plus": ["0 0 16 16", "<path d=\"M8 3v10M3 8h10\"/>"], "i-search": ["0 0 16 16", "<path d=\"M7 2.5a4.5 4.5 0 1 0 0 9 4.5 4.5 0 1 0 0-9zM10.4 10.4L14 14\"/>"], "i-sort": ["0 0 16 16", "<path d=\"M4.5 6.5h7L8 2.5zM4.5 9.5h7L8 13.5z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-sort-d": ["-4.09 -3.13 31 31", "<path transform=\"rotate(45 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-more": ["0 0 16 16", "<path d=\"M3 7h2v2H3zM7 7h2v2H7zM11 7h2v2h-2z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-home": ["0 0 16 16", "<path d=\"M2 7.5L8 2.5l6 5V14H2zM6.5 14v-4h3v4\"/>"], "i-grid": ["0 0 16 16", "<path d=\"M2 2h5v5H2zM9 2h5v5H9zM2 9h5v5H2zM9 9h5v5H9z\"/>"], "i-list": ["0 0 16 16", "<path d=\"M2 3.5h12M2 8h12M2 12.5h8\"/>"], "i-box": ["0 0 16 16", "<path d=\"M8 1.8l6 3v6.4l-6 3-6-3V4.8zM2 4.8l6 3 6-3M8 7.8v6.4\"/>"], "i-user": ["0 0 16 16", "<path d=\"M5.5 2h5v5h-5zM2.5 14.5V12l2.5-2.5h6l2.5 2.5v2.5\"/>"], "i-sliders": ["0 0 16 16", "<path d=\"M2 4h6M11 4h3M9.5 2.5v3M2 12h2M7 12h7M5.5 10.5v3\"/>"], "i-doc": ["0 0 16 16", "<path d=\"M3 1.5h7l3 3v10H3zM10 1.5v3h3M5.5 8h5M5.5 11h5\"/>"], "i-upload": ["0 0 16 16", "<path d=\"M2.5 14.5h11\"/><path transform=\"translate(8 7.2) scale(.34) rotate(-135) translate(-11.5 -11.6)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-filter": ["0 0 16 16", "<path d=\"M2 2.25h12l-4.5 5.5v4.5l-3 1.5v-6z\"/>"], "i-inbox": ["0 0 16 16", "<path d=\"M1.5 9.5l2-7h9l2 7V14h-13zM1.5 9.5h4l1 2h3l1-2h4\"/>"], "i-refresh": ["0 0 16 16", "<path d=\"M13 2.5v4H9M12.7 6.3A5 5 0 1 0 13 9.5\"/>"], "i-menu": ["0 0 16 16", "<path d=\"M2 4h12M2 8h12M2 12h12\"/>"], "i-trash": ["0 0 16 16", "<path d=\"M2.5 4h11M6 4V2h4v2M4 4l.7 10h6.6L12 4M6.8 7v4.5M9.2 7v4.5\"/>"], "n-home": ["0 0 40 40", "<path fill-rule=\"evenodd\" fill=\"currentColor\" d=\"M35.744,33.156 L39.625,29.275 L31.369,21.019 L31.369,18.013 L39.616,9.766 L35.735,5.885 L26.176,15.443 L26.192,15.459 L26.185,15.459 L26.185,16.780 L22.854,16.780 L22.854,13.449 L24.184,13.449 L24.184,13.442 L24.191,13.449 L33.750,3.890 L29.869,0.009 L21.612,8.265 L18.606,8.265 L10.359,0.018 L6.478,3.899 L16.037,13.458 L16.053,13.442 L16.053,13.449 L17.365,13.449 L17.365,16.780 L14.042,16.780 L14.042,15.451 L14.035,15.451 L14.042,15.443 L4.484,5.885 L0.603,9.766 L8.859,18.022 L8.859,21.028 L0.612,29.275 L4.493,33.156 L14.052,23.597 L14.036,23.582 L14.042,23.582 L14.042,22.269 L17.365,22.269 L17.365,25.592 L16.044,25.592 L16.044,25.599 L16.037,25.592 L6.478,35.151 L10.359,39.032 L18.615,30.776 L21.622,30.776 L29.869,39.023 L33.750,35.142 L24.191,25.583 L24.175,25.599 L24.175,25.592 L22.854,25.592 L22.854,22.269 L26.185,22.269 L26.185,23.590 L26.193,23.590 L26.185,23.597 L35.744,33.156 Z\"></path>"], "n-operator": ["0 0 44 49", "<path fill-rule=\"evenodd\" fill=\"currentColor\" d=\"M43.057,48.470 L37.334,48.470 L6.667,48.470 L0.942,48.470 L0.942,40.719 L0.942,15.502 L0.941,15.502 L0.941,6.304 L0.942,6.304 L0.942,6.301 L6.667,6.301 L6.667,6.304 L9.743,6.304 L9.743,10.903 L34.526,10.903 L34.526,6.304 L37.334,6.304 L37.334,6.301 L43.058,6.301 L43.058,48.470 L43.057,48.470 ZM37.334,15.502 L6.667,15.502 L6.667,40.719 L10.448,40.719 L10.448,35.267 C10.448,32.112 12.951,29.554 16.037,29.554 L27.963,29.554 C31.049,29.554 33.551,32.112 33.551,35.267 L33.551,40.719 L37.334,40.719 L37.334,15.502 ZM22.000,27.793 C19.155,27.793 16.848,25.434 16.848,22.526 C16.848,19.617 19.155,17.259 22.000,17.259 C24.845,17.259 27.152,19.617 27.152,22.526 C27.152,25.434 24.845,27.793 22.000,27.793 ZM9.743,0.506 L34.526,0.506 L34.526,6.304 L9.743,6.304 L9.743,0.506 Z\"></path>"], "n-lore": ["0 0 42 42", "<path fill-rule=\"evenodd\" fill=\"currentColor\" d=\"M36.038,32.520 L36.038,5.876 L15.483,5.876 L15.483,0.188 L41.891,0.188 L41.891,32.520 L36.038,32.520 ZM15.614,9.516 L15.483,9.643 L15.483,9.787 L11.414,13.741 L6.027,8.506 L1.825,4.423 L1.861,4.388 L1.787,4.316 L6.060,0.164 L11.829,5.769 L15.445,9.283 L15.649,9.482 L15.614,9.516 ZM6.027,35.043 L22.791,35.043 L22.791,40.731 L0.173,40.731 L0.173,13.742 L6.027,13.742 L6.027,35.043 ZM15.652,24.914 L15.652,31.990 L8.255,31.990 L8.255,24.800 L15.535,24.800 L15.652,24.800 L15.652,9.476 L31.421,9.476 L31.421,24.800 L23.479,24.800 L23.479,32.518 L23.479,32.520 L15.652,24.914 ZM31.513,32.808 L34.107,35.331 L36.934,38.078 L33.068,41.835 L32.228,41.019 L26.374,35.331 L23.778,32.808 L23.479,32.518 L27.347,28.759 L31.513,32.808 Z\"></path>"], "n-calendar": ["0 0 42 40", "<path fill-rule=\"evenodd\" fill=\"currentColor\" d=\"M-0.002,40.010 L-0.002,5.448 L5.894,5.448 L5.894,10.171 L6.956,10.171 L6.956,8.485 L6.956,5.448 L6.956,-0.008 L12.072,-0.008 L12.072,5.448 L12.072,8.485 L12.072,10.171 L13.134,10.171 L13.134,5.448 L28.881,5.448 L28.881,10.171 L29.943,10.171 L29.943,8.485 L29.940,8.485 L29.940,-0.008 L35.056,-0.008 L35.056,5.448 L35.059,5.448 L35.059,10.171 L36.121,10.171 L36.121,5.448 L42.014,5.448 L42.014,40.010 L-0.002,40.010 ZM38.159,16.680 L3.853,16.680 L3.853,35.999 L38.159,35.999 L38.159,16.680 ZM9.511,22.456 L6.956,22.456 L6.956,19.889 L9.511,19.889 L9.511,22.456 ZM12.065,25.023 L9.511,25.023 L9.511,22.456 L12.065,22.456 L12.065,25.023 ZM12.065,30.156 L9.511,30.156 L9.511,27.590 L12.065,27.590 L12.065,30.156 ZM17.174,27.590 L17.174,30.156 L14.620,30.156 L14.620,27.590 L17.174,27.590 ZM22.283,27.590 L22.283,30.156 L19.729,30.156 L19.729,27.590 L22.283,27.590 ZM27.392,27.590 L27.392,30.156 L24.838,30.156 L24.838,27.590 L27.392,27.590 ZM32.501,27.590 L32.501,30.156 L29.947,30.156 L29.947,27.590 L32.501,27.590 ZM29.947,22.456 L32.501,22.456 L32.501,25.023 L29.947,25.023 L29.947,22.456 ZM24.838,25.023 L24.838,22.456 L27.392,22.456 L27.392,25.023 L24.838,25.023 ZM19.729,25.023 L19.729,22.456 L22.283,22.456 L22.283,25.023 L19.729,25.023 ZM14.620,25.023 L14.620,22.456 L17.174,22.456 L17.174,25.023 L14.620,25.023 ZM14.620,27.590 L12.065,27.590 L12.065,25.023 L14.620,25.023 L14.620,27.590 ZM19.729,25.023 L19.729,27.590 L17.174,27.590 L17.174,25.023 L19.729,25.023 ZM24.838,25.023 L24.838,27.590 L22.283,27.590 L22.283,25.023 L24.838,25.023 ZM29.947,25.023 L29.947,27.590 L27.392,27.590 L27.392,25.023 L29.947,25.023 ZM12.065,19.889 L14.620,19.889 L14.620,22.456 L12.065,22.456 L12.065,19.889 ZM17.174,19.889 L19.729,19.889 L19.729,22.456 L17.174,22.456 L17.174,19.889 ZM22.283,19.889 L24.838,19.889 L24.838,22.456 L22.283,22.456 L22.283,19.889 ZM27.392,19.889 L29.947,19.889 L29.947,22.456 L27.392,22.456 L27.392,19.889 ZM35.056,19.889 L35.056,22.456 L32.501,22.456 L32.501,19.889 L35.056,19.889 ZM35.056,25.023 L35.056,27.590 L32.501,27.590 L32.501,25.023 L35.056,25.023 ZM35.056,32.724 L32.501,32.724 L32.501,30.156 L35.056,30.156 L35.056,32.724 ZM29.947,32.724 L27.392,32.724 L27.392,30.156 L29.947,30.156 L29.947,32.724 ZM24.838,32.724 L22.283,32.724 L22.283,30.156 L24.838,30.156 L24.838,32.724 ZM19.729,32.724 L17.174,32.724 L17.174,30.156 L19.729,30.156 L19.729,32.724 ZM14.620,32.724 L12.065,32.724 L12.065,30.156 L14.620,30.156 L14.620,32.724 ZM6.956,32.724 L6.956,30.156 L9.511,30.156 L9.511,32.724 L6.956,32.724 ZM6.956,27.590 L6.956,25.023 L9.511,25.023 L9.511,27.590 L6.956,27.590 Z\"></path>"], "n-notice": ["0 0 44 49", "<path fill-rule=\"evenodd\" fill=\"currentColor\" d=\"M17.123,48.243 L17.123,8.711 L35.000,20.840 L43.285,20.840 L43.285,36.113 L35.000,36.113 L17.123,48.243 ZM9.253,0.256 L14.966,0.256 L14.966,5.930 L9.253,5.930 L9.253,0.256 ZM0.967,0.256 L6.680,0.256 L6.680,5.930 L0.967,5.930 L0.967,0.256 ZM13.264,15.581 L6.882,15.581 L6.882,41.372 L13.264,41.372 L13.264,46.884 L1.332,46.884 L1.332,10.069 L13.264,10.069 L13.264,15.581 ZM34.848,47.434 L34.848,39.054 L43.285,39.054 L34.848,47.434 Z\"></path>"], "i-bolt": ["0 0 16 16", "<path d=\"M9.5 1.5L3.5 9h4l-1 5.5 6-7.5h-4z\"/>"], "i-info-plain": ["0 0 16 16", "<path d=\"M8 7.2v5.3\"/><path d=\"M6.9 3.2h2.2v2.2H6.9z\" fill=\"currentColor\" stroke=\"none\"/>"], "k-up": ["-3.92 -4.87 31 31", "<path transform=\"rotate(-135 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "k-down": ["-4.09 -3.13 31 31", "<path transform=\"rotate(45 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "k-left": ["-4.87 -4.09 31 31", "<path transform=\"rotate(135 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "k-right": ["-3.13 -3.92 31 31", "<path transform=\"rotate(-45 11.5 11.5)\" d=\"M2.673,22.418 L2.673,19.398 L17.146,19.398 L0.740,2.992 L2.875,0.857 L19.280,17.263 L19.280,2.791 L22.300,2.791 L22.300,22.418 L2.673,22.418 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-copy": ["0 0 16 16", "<path d=\"M5 5h9v9H5zM2 11V2h9\"/>"], "i-cycle": ["0 0 16 16", "<path d=\"M5.435,3.557 A5.13,5.13 0 0 1 12.397,10.642 L10.863,9.72 A3.34,3.34 0 0 0 6.33,5.107 Z M10.642,12.397 A5.13,5.13 0 0 1 3.603,5.358 L5.137,6.28 A3.34,3.34 0 0 0 9.72,10.863 Z\" fill=\"currentColor\" stroke=\"none\"/>"], "i-pin": ["0 0 16 16", "<path fill-rule=\"evenodd\" d=\"M8,13.6 L4.85,7.95 A3.6,3.6 0 1 1 11.15,7.95 Z M9.6,6.2 A1.6,1.6 0 1 0 6.4,6.2 A1.6,1.6 0 1 0 9.6,6.2 Z\" fill=\"currentColor\" stroke=\"none\"/>"]};
function once(el,key){if(el['_ef_'+key])return false;el['_ef_'+key]=1;return true}
function all(root,sel){return [].slice.call(root.querySelectorAll(sel))}
function mountSprite(){
  if(document.getElementById('ef-sprite'))return;
  var NS='http://www.w3.org/2000/svg',svg=document.createElementNS(NS,'svg');
  svg.setAttribute('id','ef-sprite');svg.setAttribute('aria-hidden','true');svg.setAttribute('width','0');svg.setAttribute('height','0');svg.style.position='absolute';
  var h='';Object.keys(ICONS).forEach(function(k){h+='<symbol id="'+k+'" viewBox="'+ICONS[k][0]+'">'+ICONS[k][1]+'</symbol>'});
  svg.innerHTML=h;document.body.insertBefore(svg,document.body.firstChild);
}
function usable(x){return !x.disabled&&!x.classList.contains('is-disabled')&&x.getAttribute('aria-disabled')!=='true'}
function arrows(box,sel,prevKeys,nextKeys,onMove){
  box.addEventListener('keydown',function(e){
    var items=all(box,sel).filter(usable),i=items.indexOf(document.activeElement);if(i<0)return;var n=null;
    if(nextKeys.indexOf(e.key)>=0)n=items[(i+1)%items.length];
    else if(prevKeys.indexOf(e.key)>=0)n=items[(i-1+items.length)%items.length];
    else if(e.key==='Home')n=items[0];else if(e.key==='End')n=items[items.length-1];
    if(n){e.preventDefault();n.focus();if(onMove)onMove(n)}
  });
}
function toast(stack,type,msg,action){
  var t=document.createElement('div');t.className='toast';t.setAttribute('role',type==='error'?'alert':'status');
  t.innerHTML='<div class="msg"></div>'+(action?'<button class="act" type="button"></button>':'')+'<button class="x" type="button" aria-label="关闭"><svg class="ic ic--close"><use href="#i-close"/></svg></button>';
  t.querySelector('.msg').textContent=msg;if(action)t.querySelector('.act').textContent=action;
  while(stack.children.length>=3)stack.removeChild(stack.firstChild);
  stack.appendChild(t);
  var ms=type==='error'?0:(action?8000:4000),timer=null;
  function arm(){if(ms)timer=setTimeout(function(){t.remove()},ms)}
  t.addEventListener('mouseenter',function(){clearTimeout(timer)});t.addEventListener('mouseleave',arm);arm();
  t.addEventListener('click',function(e){if(e.target.closest('.x')||e.target.closest('.act'))t.remove()});
  return t;
}
function init(root){
  root=root||document;mountSprite();
  all(root,'input[data-indet]').forEach(function(i){i.indeterminate=true});
  /* 标签页：点击与方向键 */
  all(root,'[data-tabs]').forEach(function(list){if(!once(list,'tabs'))return;
    function sel(t){all(list,'[role=tab]').forEach(function(x){var on=x===t;x.setAttribute('aria-selected',String(on));x.tabIndex=on?0:-1})}
    var cur=list.querySelector('[aria-selected=true]');if(cur)sel(cur);
    list.addEventListener('click',function(e){var t=e.target.closest('[role=tab]');if(t&&!t.disabled)sel(t)});
    arrows(list,'[role=tab]',['ArrowLeft'],['ArrowRight'],sel);
  });
  /* 主标签栏 Q/E */
  all(root,'[data-qe]').forEach(function(bar){if(!once(bar,'qe'))return;bar.addEventListener('keydown',function(e){var k=e.key.toLowerCase();if(k!=='q'&&k!=='e')return;
    var tabs=all(bar,'[role=tab]'),i=tabs.findIndex(function(t){return t.getAttribute('aria-selected')==='true'});
    var n=tabs[(i+(k==='e'?1:-1)+tabs.length)%tabs.length];n.click();n.focus();e.preventDefault()})});
  /* 分段控件 */
  all(root,'[data-seg]').forEach(function(g){if(!once(g,'seg'))return;
    g.addEventListener('click',function(e){var b=e.target.closest('button');if(!b)return;all(g,'button').forEach(function(x){x.setAttribute('aria-pressed',String(x===b))})});});
  /* 下拉选择 */
  all(root,'[data-dd]').forEach(function(dd){if(!once(dd,'dd'))return;
    var trig=dd.querySelector('.select'),menu=dd.querySelector('.menu'),val=dd.querySelector('[data-val]');
    function close(){menu.hidden=true;trig.setAttribute('aria-expanded','false')}
    trig.addEventListener('click',function(){var open=menu.hidden;menu.hidden=!open;trig.setAttribute('aria-expanded',String(open));if(open){var s=menu.querySelector('[aria-selected=true]');if(s)s.focus()}});
    menu.addEventListener('click',function(e){var it=e.target.closest('.menu-item');if(!it||it.classList.contains('is-disabled'))return;
      all(menu,'.menu-item').forEach(function(x){x.setAttribute('aria-selected',String(x===it))});if(val)val.textContent=it.firstChild.textContent;close();trig.focus()});
    document.addEventListener('click',function(e){if(!dd.contains(e.target))close()});
    dd.addEventListener('keydown',function(e){if(e.key==='Escape'&&!menu.hidden){close();trig.focus()}});
    arrows(menu,'.menu-item',['ArrowUp'],['ArrowDown']);
  });
  /* 多行文本计数：<textarea data-max="200"> 与同一 .field 内的 .count */
  all(root,'textarea[data-max]').forEach(function(ta){if(!once(ta,'cnt'))return;var f=ta.closest('.field'),c=f&&f.querySelector('.count');if(!c)return;
    function upd(){c.textContent=ta.value.length+'/'+ta.dataset.max}ta.addEventListener('input',upd);upd()});
  /* 轻提示：按钮 data-toast="success|error|warning|info"，data-msg 文案，data-action 操作；插入同一根节点内的 .toast-stack */
  all(root,'[data-toast]').forEach(function(b){if(!once(b,'toast'))return;b.addEventListener('click',function(){
    var stack=root.querySelector('.toast-stack');if(!stack)return;toast(stack,b.dataset.toast,b.dataset.msg||'',b.dataset.action||'')})});
  /* 对话框：data-open="<dialog id>"；对话框内 data-close 关闭；危险确认 input[data-confirm] 输入正确值后启用 [data-confirm-go] */
  all(root,'[data-open]').forEach(function(b){if(!once(b,'open'))return;b.addEventListener('click',function(){var d=document.getElementById(b.dataset.open);if(d&&d.showModal)d.showModal()})});
  all(root,'dialog').forEach(function(d){if(!once(d,'dlg'))return;
    var inp=d.querySelector('input[data-confirm]'),go=d.querySelector('[data-confirm-go]');
    if(inp&&go){inp.addEventListener('input',function(){go.disabled=inp.value.trim()!==inp.dataset.confirm});d.addEventListener('close',function(){inp.value='';go.disabled=true})}
    d.addEventListener('click',function(e){if(e.target.closest('[data-close]'))d.close()})});
  /* 分页器 */
  all(root,'[data-pager]').forEach(function(pager){if(!once(pager,'pager'))return;
    pager.addEventListener('click',function(e){var b=e.target.closest('.pg');if(!b)return;var pages=all(pager,'.pg:not([data-prev]):not([data-next])');
      var cur=pages.findIndex(function(p){return p.hasAttribute('aria-current')}),next=cur;
      if(b.hasAttribute('data-prev'))next=Math.max(0,cur-1);else if(b.hasAttribute('data-next'))next=Math.min(pages.length-1,cur+1);else next=pages.indexOf(b);
      pages.forEach(function(p,i){if(i===next)p.setAttribute('aria-current','page');else p.removeAttribute('aria-current')});
      var pv=pager.querySelector('[data-prev]'),nx=pager.querySelector('[data-next]');if(pv)pv.disabled=next===0;if(nx)nx.disabled=next===pages.length-1;})});
  /* 翻页胶囊 */
  /* 翻页胶囊：页码一次排好，窗口显示 4 个；当前页越出窗口时整排平移，使其刚好落在窗口边缘。 */
  all(root,'[data-pcap]').forEach(function(c){if(!once(c,'pcap'))return;
    var total=+c.dataset.total,car=c.querySelector('.pcar'),off=0,h='';
    for(var n=1;n<=total;n++){h+='<span class="pblk" style="--i:'+(n-1)+'">'+(n<10?'0':'')+n+'</span>'}
    car.innerHTML=h;car.style.setProperty('--n',Math.min(total,4));
    function draw(){var cur=+c.dataset.pcap;
      if(cur-1<off)off=cur-1;if(cur-1>off+3)off=cur-4;off=Math.max(0,Math.min(off,Math.max(0,total-4)));
      car.style.setProperty('--off',off);
      all(car,'.pblk').forEach(function(b,i){if(i===cur-1)b.setAttribute('aria-current','page');else b.removeAttribute('aria-current')});
      c.querySelector('[data-step="-1"]').disabled=cur<=1;c.querySelector('[data-step="1"]').disabled=cur>=total}
    c.addEventListener('click',function(e){var b=e.target.closest('[data-step]');if(!b)return;c.dataset.pcap=Math.min(total,Math.max(1,+c.dataset.pcap+ +b.dataset.step));draw()});
    draw();});
  /* 可选卡片、列表、入口菜单 */
  all(root,'[data-selectable]').forEach(function(c){if(!once(c,'selc'))return;c.addEventListener('click',function(){c.setAttribute('aria-pressed',String(c.getAttribute('aria-pressed')!=='true'))})});
  all(root,'[data-list]').forEach(function(l){if(!once(l,'list'))return;
    function pick(li){if(!li||li.classList.contains('is-disabled'))return;all(l,'.li').forEach(function(x){x.setAttribute('aria-selected',String(x===li))});all(l,'.is-hover').forEach(function(x){x.classList.remove('is-hover')})}
    l.addEventListener('click',function(e){pick(e.target.closest('.li'))});
    l.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();pick(e.target.closest('.li'))}});
    arrows(l,'.li',['ArrowUp'],['ArrowDown']);});
  /* 竖向开关 */
  all(root,'.vswitch').forEach(function(v){if(!once(v,'vswitch'))return;
    function flip(){v.setAttribute('aria-checked',String(v.getAttribute('aria-checked')!=='true'))}
    v.addEventListener('click',flip);
    v.addEventListener('keydown',function(e){if(e.key==='Enter'||e.key===' '){e.preventDefault();flip()}});});
  all(root,'[data-smenu]').forEach(function(m){if(!once(m,'smenu'))return;m.addEventListener('click',function(e){var b=e.target.closest('.smi');if(!b)return;
    all(m,'.smi').forEach(function(x){if(x===b)x.setAttribute('aria-current','true');else x.removeAttribute('aria-current')})})});
  /* 表格：单击表头排序，再次单击反转；单击行或按空格、回车切换选中，Shift 加单击连续选中；表头左侧方块全选；Ctrl/Cmd+A 全选，Esc 清除；上下方向键移动焦点，跳过禁用行 */
  all(root,'table.tbl').forEach(function(tb){if(!once(tb,'tbl'))return;
    var body=tb.tBodies[0],multi=tb.getAttribute('aria-multiselectable')==='true',allBtn=null,last=null;
    function live(){return all(body,'tr').filter(function(tr){return tr.getAttribute('aria-disabled')!=='true'})}
    function sync(){if(!allBtn)return;var r=live(),n=r.filter(function(tr){return tr.getAttribute('aria-selected')==='true'}).length;
      allBtn.setAttribute('aria-checked',String(n>0&&n===r.length))}
    function fire(){sync();tb.dispatchEvent(new CustomEvent('tbl-select',{bubbles:true}))}
    function setAll(on){live().forEach(function(tr){tr.setAttribute('aria-selected',String(on))});fire()}
    function prep(tr){if(!multi)return;if(tr.getAttribute('aria-disabled')==='true'){tr.removeAttribute('tabindex');tr.removeAttribute('aria-selected');return}
      if(!tr.hasAttribute('tabindex'))tr.tabIndex=0;if(!tr.hasAttribute('aria-selected'))tr.setAttribute('aria-selected','false')}
    all(body,'tr').forEach(prep);
    if(multi&&tb.tHead){var th0=tb.tHead.rows[0].cells[0];allBtn=document.createElement('button');allBtn.type='button';allBtn.className='tbl-all';
      allBtn.setAttribute('role','checkbox');allBtn.setAttribute('aria-label','全选');th0.insertBefore(allBtn,th0.firstChild);
      allBtn.addEventListener('click',function(e){e.stopPropagation();setAll(allBtn.getAttribute('aria-checked')!=='true')});sync()}
    function cellVal(tr,i,num){var c=tr.cells[i],v=c.getAttribute('data-value')!=null?c.getAttribute('data-value'):c.textContent;
      if(num){v=parseFloat(String(v).replace(/[^\d.-]/g,''));return isNaN(v)?-Infinity:v}return v.trim()}
    tb.tHead.addEventListener('click',function(e){var b=e.target.closest('button');if(!b||b===allBtn)return;
      var th=b.closest('th'),i=th.cellIndex,num=th.classList.contains('num'),cur=th.getAttribute('aria-sort');
      var dir=cur==='descending'?1:cur==='ascending'?-1:(num?-1:1);
      all(tb,'thead th').forEach(function(h){if(h!==th)h.removeAttribute('aria-sort')});
      th.setAttribute('aria-sort',dir>0?'ascending':'descending');
      all(body,'tr').sort(function(x,y){var a=cellVal(x,i,num),c=cellVal(y,i,num);
        var r=num?a-c:String(a).localeCompare(String(c),'zh-Hans-CN');return r*dir||cellVal(x,0).localeCompare(cellVal(y,0))})
        .forEach(function(tr){body.appendChild(tr)})});
    function toggle(tr,range){if(!multi||!tr||tr.getAttribute('aria-disabled')==='true'||!body.contains(tr))return;
      var on=tr.getAttribute('aria-selected')!=='true',rows=all(body,'tr'),a=rows.indexOf(last),b=rows.indexOf(tr);
      if(range&&a>=0&&a!==b)rows.slice(Math.min(a,b),Math.max(a,b)+1).forEach(function(x){if(x.getAttribute('aria-disabled')!=='true')x.setAttribute('aria-selected',String(on))});
      else tr.setAttribute('aria-selected',String(on));
      last=tr;fire()}
    body.addEventListener('click',function(e){if(e.target.closest('button,a,input,label,select,textarea'))return;toggle(e.target.closest('tr'),e.shiftKey)});
    tb.addEventListener('keydown',function(e){if(!multi||!body.contains(e.target))return;
      if((e.ctrlKey||e.metaKey)&&e.key.toLowerCase()==='a'){e.preventDefault();setAll(true)}else if(e.key==='Escape'){setAll(false)}});
    body.addEventListener('keydown',function(e){var tr=e.target.closest('tr');if(!tr)return;
      if(!multi||e.target!==tr)return;
      if(e.key===' '||e.key==='Enter'){e.preventDefault();toggle(tr,e.shiftKey)}
      else if(e.key==='ArrowDown'||e.key==='ArrowUp'){e.preventDefault();var n=tr;
        do{n=e.key==='ArrowDown'?n.nextElementSibling:n.previousElementSibling}while(n&&n.getAttribute('aria-disabled')==='true');if(n)n.focus()}});
    tb.Endfield={prep:function(tr){prep(tr);sync()},selected:function(){return all(body,'tr[aria-selected="true"]')},selectAll:function(){setAll(true)},clear:function(){setAll(false)}}});
  /* 切换型图标按钮、清除按钮 */
  all(root,'.ibtn[aria-pressed]').forEach(function(b){if(!once(b,'tg'))return;b.addEventListener('click',function(){var on=b.getAttribute('aria-pressed')!=='true';b.setAttribute('aria-pressed',String(on));b.classList.toggle('is-pressed',on)})});
  all(root,'.clear').forEach(function(b){if(!once(b,'clr'))return;b.addEventListener('click',function(){var i=b.parentNode.querySelector('input');if(i){i.value='';i.focus()}})});
  /* 侧边导航 */
  all(root,'[data-sn]').forEach(function(sn){if(!once(sn,'sn'))return;
    var tg=sn.querySelector('.sn-toggle'),list=sn.querySelector('.sn-list'),pinned=false;
    function set(open){sn.classList.toggle('is-open',open);tg.setAttribute('aria-expanded',String(open));tg.setAttribute('aria-label',open?'收起导航':'展开导航')}
    sn.addEventListener('mouseenter',function(){set(true)});
    sn.addEventListener('mouseleave',function(){if(!pinned&&!sn.contains(document.activeElement))set(false)});
    sn.addEventListener('focusin',function(){set(true)});
    sn.addEventListener('focusout',function(e){if(!pinned&&!sn.contains(e.relatedTarget)&&!sn.matches(':hover'))set(false)});
    tg.addEventListener('click',function(){pinned=!pinned;set(pinned)});
    list.addEventListener('click',function(e){var a=e.target.closest('.sn-item');if(!a)return;e.preventDefault();
      all(list,'.sn-item').forEach(function(x){if(x===a)x.setAttribute('aria-current','page');else x.removeAttribute('aria-current')});
      list.style.setProperty('--y',a.offsetTop+'px')});});
  all(root,'.sn-list').forEach(function(list){var c=list.querySelector('.sn-item[aria-current]');if(c)list.style.setProperty('--y',c.offsetTop+'px')});
  /* 页面加载 */
  all(root,'[data-ldr]').forEach(function(l){if(!once(l,'ldr'))return;runLoader(l)});
  all(root,'[data-ldr-replay]').forEach(function(b){if(!once(b,'rp'))return;b.addEventListener('click',function(){all(root,'[data-ldr]').forEach(runLoader)})});
  /* 间距样例：按容器宽度缩放，标注开关 */
  var spx=all(root,'.spx[data-w]');function fit(){spx.forEach(function(x){var w=+x.dataset.w,z=Math.min(1,x.clientWidth/w),inner=x.querySelector('.spx-z');x.style.setProperty('--sw',w);x.style.setProperty('--z',z);x.style.setProperty('--sh',inner.offsetHeight*z+'px')})}
  if(spx.length){fit();window.addEventListener('resize',fit);if(window.ResizeObserver)spx.forEach(function(x){new ResizeObserver(fit).observe(x.querySelector('.spx-z'))})}
  all(root,'[data-sp-toggle]').forEach(function(t){if(!once(t,'spt'))return;t.addEventListener('change',function(){all(root,'.spx').forEach(function(x){x.classList.toggle('is-marked',t.checked)})})});
}
function runLoader(l){
  var sc=l.querySelector('.ldr-screen'),num=sc.querySelector('.ldr-core b'),p=0;
  clearInterval(l._t);clearTimeout(l._d);sc.classList.remove('is-leaving','is-done');
  function set(v){sc.style.setProperty('--p',v);num.textContent=v;sc.setAttribute('aria-valuenow',v)}
  set(0);
  l._t=setInterval(function(){p=Math.min(100,p+Math.ceil(Math.random()*(p<80?12:5)));set(p);
    if(p>=100){clearInterval(l._t);sc.classList.add('is-leaving');l._d=setTimeout(function(){sc.classList.add('is-done')},1600)}},160);
}
/* 全局：刷新图标点击转一周；悬浮说明 Esc 隐藏 */
document.addEventListener('click',function(e){var b=e.target.closest&&e.target.closest('button');if(!b)return;var ic=b.querySelector('.ic--refresh');if(!ic)return;
  ic.classList.remove('is-turning');void ic.getBoundingClientRect();ic.classList.add('is-turning')});
document.addEventListener('animationend',function(e){var t=e.target;if(t.classList&&t.classList.contains('is-turning'))t.classList.remove('is-turning')});
document.addEventListener('keydown',function(e){if(e.key!=='Escape')return;var h=document.activeElement&&document.activeElement.closest('.tip-host');if(h)h.classList.add('tip-off')});
document.addEventListener('focusout',function(e){var h=e.target.closest&&e.target.closest('.tip-host');if(h)h.classList.remove('tip-off')});
window.Endfield={icons:ICONS,init:init,toast:function(type,msg,action,stack){return toast(stack||document.querySelector('.toast-stack'),type,msg,action)},runLoader:runLoader};
})();
