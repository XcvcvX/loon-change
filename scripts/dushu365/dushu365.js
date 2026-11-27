// Dushu365 (FanShu) response optimizer
// Upstream: zirawell/R-Store cfd273d27fdb73dd9dd3f21264e0ba01e8ffbadd
// Active plugin routes: DUSHU365-2/-4/-7/-8/-9 only.
// https://www.npmjs.com/package/base-64
// prettier-ignore
!function(r){var t=function(r){this.message=r};(t.prototype=new Error).name="InvalidCharacterError";var e=function(r){throw new t(r)},a="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/",n=/[\t\n\f\r ]/g,c={encode:function(r){r=String(r),/[^\0-\xFF]/.test(r)&&e("The string to be encoded contains characters outside of the Latin1 range.");for(var t,n,c,o,h=r.length%3,d="",i=-1,A=r.length-h;++i<A;)t=r.charCodeAt(i)<<16,n=r.charCodeAt(++i)<<8,c=r.charCodeAt(++i),d+=a.charAt((o=t+n+c)>>18&63)+a.charAt(o>>12&63)+a.charAt(o>>6&63)+a.charAt(63&o);return 2==h?(t=r.charCodeAt(i)<<8,n=r.charCodeAt(++i),d+=a.charAt((o=t+n)>>10)+a.charAt(o>>4&63)+a.charAt(o<<2&63)+"="):1==h&&(o=r.charCodeAt(i),d+=a.charAt(o>>2)+a.charAt(o<<4&63)+"=="),d},decode:function(r){var t=(r=String(r).replace(n,"")).length;t%4==0&&(t=(r=r.replace(/==?$/,"")).length),(t%4==1||/[^+a-zA-Z0-9/]/.test(r))&&e("Invalid character: the string to be decoded is not correctly encoded.");for(var c,o,h=0,d="",i=-1;++i<t;)o=a.indexOf(r.charAt(i)),c=h%4?64*c+o:o,h++%4&&(d+=String.fromCharCode(255&c>>(-2*h&6)));return d},version:"1.0.0"};r.base64=c}(globalThis);
// https://www.npmjs.com/package/utf8
// prettier-ignore
!function(r){var n,t,o,e=String.fromCharCode;function i(r){for(var n,t,o=[],e=0,i=r.length;e<i;)(n=r.charCodeAt(e++))>=55296&&n<=56319&&e<i?56320==(64512&(t=r.charCodeAt(e++)))?o.push(((1023&n)<<10)+(1023&t)+65536):(o.push(n),e--):o.push(n);return o}function u(r){if(r>=55296&&r<=57343)throw Error("Lone surrogate U+"+r.toString(16).toUpperCase()+" is not a scalar value")}function f(r,n){return e(r>>n&63|128)}function a(r){if(!(4294967168&r))return e(r);var n="";return 4294965248&r?4294901760&r?4292870144&r||(n=e(r>>18&7|240),n+=f(r,12),n+=f(r,6)):(u(r),n=e(r>>12&15|224),n+=f(r,6)):n=e(r>>6&31|192),n+=e(63&r|128)}function c(){if(o>=t)throw Error("Invalid byte index");var r=255&n[o];if(o++,128==(192&r))return 63&r;throw Error("Invalid continuation byte")}function h(){var r,e;if(o>t)throw Error("Invalid byte index");if(o==t)return!1;if(r=255&n[o],o++,!(128&r))return r;if(192==(224&r)){if((e=(31&r)<<6|c())>=128)return e;throw Error("Invalid continuation byte")}if(224==(240&r)){if((e=(15&r)<<12|c()<<6|c())>=2048)return u(e),e;throw Error("Invalid continuation byte")}if(240==(248&r)&&((e=(7&r)<<18|c()<<12|c()<<6|c())>=65536&&e<=1114111))return e;throw Error("Invalid UTF-8 detected")}let d={version:"3.0.0",encode:function(r){for(var n=i(r),t=n.length,o=-1,e="";++o<t;)e+=a(n[o]);return e},decode:function(r){n=i(r),t=n.length,o=0;for(var u,f=[];!1!==(u=h());)f.push(u);return function(r){for(var n,t=r.length,o=-1,i="";++o<t;)(n=r[o])>65535&&(i+=e((n-=65536)>>>10&1023|55296),n=56320|1023&n),i+=e(n);return i}(f)}};r.utf8=d}(globalThis);

const pathMatch = /^(?:https?:\/\/)?[^/]+(\/[^?#]*)?/.exec($request.url || "");
const pathname = pathMatch && pathMatch[1] || "";
const route =
    pathname.includes("/abtest-front/banner-modular/get") ? 2 :
    pathname.includes("/fs-member/user/profile/v100/detail") ? 4 :
    pathname.includes("/task-orchestration/taskCenter/api/v101/taskList") ? 7 :
    pathname.includes("/resource-orchestration-system/book/v101/content") ? 8 :
    pathname.includes("/user-orchestration/user/api/v101/ceiltip") ? 9 : 0;

if (!route || ($response.status ?? $request.statusCode) !== 200) {
    $done({});
} else {
    const headers = $response.headers || {};
    const encrypted = String(headers.reqentryption ?? headers.reqEntryption ?? "").toLowerCase() === "base64";
    let data;
    try {
        const raw = encrypted ? utf8.decode(base64.decode($response.body)) : $response.body;
        data = JSON.parse(String(raw));
    } catch (_) {
        $done({});
    }

    if (data !== undefined) {
        let changed = false;
        const payload = data && data.data;
        if (route === 2) {
            const banners = payload && payload.banners;
            if (Array.isArray(banners) && banners.length) { payload.banners = []; changed = true; }
        } else if (route === 4) {
            if (payload && (!Array.isArray(payload.vipInfos) || payload.vipInfos.length)) { payload.vipInfos = []; changed = true; }
        } else if (route === 7) {
            if (payload && (!Array.isArray(payload.taskInfoList) || payload.taskInfoList.length)) { payload.taskInfoList = []; changed = true; }
        } else if (route === 8) {
            const components = payload && payload.bookComponent;
            if (Array.isArray(components)) for (const item of components) {
                if (item && Object.prototype.hasOwnProperty.call(item, "compBanner")) { delete item.compBanner; changed = true; }
            }
        } else if (route === 9 && data.data !== true) {
            data.data = true; changed = true;
        }
        if (changed) {
            try {
                const json = JSON.stringify(data);
                $done({ body: encrypted ? base64.encode(utf8.encode(json)) : json });
            } catch (_) { $done({}); }
        } else { $done({}); }
    }
}
