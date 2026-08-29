<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VER Weekly Build Plan</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.2.0/umd/react.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.2.0/umd/react-dom.production.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/babel-standalone/7.23.2/babel.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-app-compat.js"></script>
<script src="https://www.gstatic.com/firebasejs/10.12.2/firebase-firestore-compat.js"></script>
<script>
const firebaseConfig={apiKey:"AIzaSyB3UgrV8_kxQDJvyMbwZ_QXVLjsgt0yilQ",authDomain:"smi-production-report.firebaseapp.com",projectId:"smi-production-report",storageBucket:"smi-production-report.firebasestorage.app",messagingSenderId:"934983410817",appId:"1:934983410817:web:77a10c77b6ee36c9ded980"};
firebase.initializeApp(firebaseConfig);
const db=firebase.firestore();
</script>
<style>
  body { margin:0; background:#f8fafc; font-family:system-ui,sans-serif; }
  ::-webkit-scrollbar{width:6px;height:6px}
  ::-webkit-scrollbar-track{background:#e2e8f0}
  ::-webkit-scrollbar-thumb{background:#cbd5e1;border-radius:3px}
</style>
</head>
<body>
<div id="root"></div>
<script type="text/babel">
const { useState, useMemo, useCallback, useEffect } = React;

// Bucket a YYYY-MM-DD date string to its Monday (week start)
function toMonday(dateStr) {
  const d = new Date(dateStr + 'T00:00:00');
  const day = d.getDay(); // 0=Sun,1=Mon,...
  const diff = (day === 0) ? -6 : 1 - day;
  d.setDate(d.getDate() + diff);
  return d.toISOString().slice(0, 10);
}

const INITIAL_DATA = [{"resource":"LPS3 HDMI","part_id":"VER1/0270-0938","description":"LoPro S3 HDMI","weeks":{"2026-08-24":750,"2026-08-31":1050,"2026-09-07":750,"2026-09-14":1050,"2026-09-21":1050,"2026-09-28":1050,"2026-10-05":1050,"2026-10-12":900,"2026-10-19":900,"2026-10-26":900,"2026-11-02":1050,"2026-11-09":1050,"2026-11-16":1050,"2026-11-23":1050,"2026-11-30":1050,"2026-12-07":1050,"2026-12-14":1050,"2026-12-21":300,"2026-12-28":300,"2027-01-04":1050,"2027-01-11":900,"2027-01-18":900,"2027-01-25":1050,"2027-02-01":1050,"2027-02-08":1050,"2027-02-15":1050,"2027-02-22":1050,"2027-03-01":1050,"2027-03-08":1050,"2027-03-15":1050,"2027-03-22":1050,"2027-03-29":750,"2027-04-05":750,"2027-04-12":750,"2027-04-19":750,"2027-04-26":750,"2027-05-03":600,"2027-05-10":600,"2027-05-17":600,"2027-05-24":600,"2027-05-31":600,"2027-06-07":600,"2027-06-14":600,"2027-06-21":600,"2027-06-28":450,"2027-07-05":450,"2027-07-12":600,"2027-07-19":450,"2027-07-26":450,"2027-08-02":450,"2027-08-09":450,"2027-08-16":450,"2027-08-23":450,"2027-08-30":450,"2027-09-06":450,"2027-09-13":450,"2027-09-20":450,"2027-09-27":450,"2027-10-04":450,"2027-10-11":450}},{"resource":"LPS3 HDMI","part_id":"VER1/0270-1078","description":"Non Sterile LoPro S3","weeks":{"2026-08-24":750,"2026-08-31":150,"2026-09-07":150,"2026-09-14":150,"2026-09-21":150,"2026-09-28":150,"2026-10-05":150,"2026-10-19":300,"2026-10-26":300,"2026-11-02":150,"2026-11-09":150,"2026-11-16":150,"2026-11-23":150,"2026-11-30":150,"2026-12-07":150,"2026-12-14":150,"2027-01-04":150,"2027-01-11":300,"2027-01-18":300,"2027-01-25":150,"2027-02-01":150,"2027-02-08":150,"2027-02-15":150,"2027-02-22":150,"2027-03-01":300,"2027-03-08":150,"2027-03-15":150,"2027-03-22":150,"2027-03-29":150,"2027-04-05":150,"2027-04-12":150,"2027-04-19":150,"2027-04-26":150,"2027-05-03":300,"2027-05-10":300,"2027-05-17":150,"2027-05-24":150,"2027-05-31":150,"2027-06-07":150,"2027-06-14":150,"2027-06-21":150,"2027-06-28":300,"2027-07-05":300,"2027-07-12":150,"2027-07-19":150,"2027-07-26":150,"2027-08-02":150,"2027-08-09":150,"2027-08-16":150,"2027-08-23":150,"2027-08-30":150,"2027-09-06":150,"2027-09-13":150,"2027-09-20":150,"2027-09-27":150,"2027-10-04":150,"2027-10-11":150}},{"resource":"QCS3","part_id":"VER1/0270-1083","description":"SpectrumQC HA S3","weeks":{"2026-08-31":2700,"2026-09-07":2100,"2026-09-14":2700,"2026-09-21":2700,"2026-09-28":2700,"2026-10-05":2700,"2026-10-12":2100,"2026-10-19":2700,"2026-10-26":2700,"2026-11-02":2700,"2026-11-09":2700,"2026-11-16":2700,"2026-11-23":2700,"2026-11-30":2700,"2026-12-07":2700,"2026-12-14":1500,"2026-12-21":1500,"2026-12-28":4050,"2027-01-04":2700,"2027-01-11":4050,"2027-01-18":2700,"2027-01-25":2700,"2027-02-01":2700,"2027-02-08":4050,"2027-02-15":2700,"2027-02-22":2700,"2027-03-01":2700,"2027-03-08":2700,"2027-03-15":2700,"2027-03-22":2700,"2027-03-29":4050,"2027-04-05":2700,"2027-04-12":2700,"2027-04-19":2700,"2027-04-26":4050,"2027-05-03":2700,"2027-05-10":4050,"2027-05-17":2700,"2027-05-24":4050,"2027-05-31":2700,"2027-06-07":4050,"2027-06-14":2700,"2027-06-21":4050,"2027-06-28":2700,"2027-07-05":2700,"2027-07-12":4050,"2027-07-19":2700,"2027-07-26":2700,"2027-08-02":2700,"2027-08-09":4050,"2027-08-16":2700,"2027-08-23":2700,"2027-08-30":2700,"2027-09-06":2700,"2027-09-13":2700,"2027-09-20":2700}},{"resource":"QC MAC3","part_id":"VER1/0270-1085","description":"Spectrum QC MACS3","weeks":{"2026-08-24":750,"2026-08-31":750,"2026-09-07":450,"2026-09-21":750,"2026-09-28":750,"2026-10-12":750,"2026-10-26":750,"2026-11-02":750,"2026-11-09":750,"2026-11-16":750,"2026-11-30":750,"2026-12-21":450,"2026-12-28":450,"2027-01-04":750,"2027-01-11":750,"2027-01-25":750,"2027-02-01":750,"2027-02-08":750,"2027-02-22":900,"2027-03-01":900,"2027-03-15":600,"2027-03-22":900,"2027-03-29":900,"2027-04-12":900,"2027-04-26":900,"2027-05-03":900,"2027-05-10":900,"2027-05-17":900,"2027-05-31":900,"2027-06-21":900,"2027-07-05":900,"2027-07-12":900,"2027-07-26":900,"2027-08-02":900,"2027-08-09":300,"2027-08-16":900,"2027-08-23":900,"2027-09-06":900,"2027-09-13":900,"2027-09-27":900,"2027-10-11":900}},{"resource":"QC MAC3","part_id":"VER1/0270-1147","description":"QC MAC S3 - NS","weeks":{"2026-09-07":300,"2026-09-14":750,"2026-10-05":750,"2026-10-19":750,"2026-11-23":750,"2026-12-07":750,"2026-12-14":750,"2027-01-18":750,"2027-02-15":750,"2027-03-08":900,"2027-03-15":300,"2027-04-05":900,"2027-04-19":900,"2027-05-24":900,"2027-06-07":900,"2027-06-14":900,"2027-06-28":900,"2027-07-19":900,"2027-08-09":600,"2027-08-30":900,"2027-09-20":900,"2027-10-04":900}},{"resource":"QC MAC4","part_id":"VER1/0270-1086","description":"Spectrum QC MACS4","weeks":{"2026-08-24":300,"2026-08-31":900,"2026-09-07":600,"2026-09-14":600,"2026-09-21":750,"2026-10-12":750,"2026-11-02":750,"2026-11-16":750,"2026-11-23":750,"2026-12-07":750,"2026-12-14":750,"2027-01-04":750,"2027-01-18":750,"2027-02-01":750,"2027-02-08":900,"2027-02-22":750,"2027-03-08":750,"2027-03-22":750,"2027-03-29":750,"2027-04-05":750,"2027-04-19":900,"2027-04-26":150,"2027-05-03":900,"2027-05-17":900,"2027-05-31":900,"2027-06-07":150,"2027-06-14":900,"2027-06-21":150,"2027-06-28":900,"2027-07-05":150,"2027-07-12":900,"2027-07-19":150,"2027-07-26":900,"2027-08-02":300,"2027-08-09":900,"2027-08-16":150,"2027-08-23":900,"2027-08-30":150,"2027-09-06":900,"2027-09-13":150,"2027-09-20":900}},{"resource":"QC MAC4","part_id":"VER1/0270-1148","description":"QC MAC S4 - NS","weeks":{"2026-08-24":300,"2026-09-07":300,"2026-09-14":300,"2026-09-28":750,"2026-10-05":750,"2026-10-19":750,"2026-10-26":750,"2026-11-09":750,"2026-11-30":750,"2026-12-21":450,"2026-12-28":450,"2027-01-11":750,"2027-01-25":750,"2027-02-15":750,"2027-03-01":750,"2027-03-15":750,"2027-04-12":750,"2027-04-26":750,"2027-05-10":900,"2027-05-24":900,"2027-06-07":750,"2027-06-21":750,"2027-07-05":750,"2027-07-19":750,"2027-08-02":450,"2027-08-16":750,"2027-08-30":750,"2027-09-13":750}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-0939","description":"LoPro S4 Short Well","weeks":{"2026-08-24":300,"2026-08-31":300,"2026-09-07":750,"2026-09-14":300,"2026-09-21":600,"2026-09-28":450,"2026-10-05":300,"2026-10-12":450,"2026-10-19":750,"2026-10-26":750,"2026-11-02":600,"2026-11-09":750,"2026-11-16":600,"2026-11-23":450,"2026-11-30":750,"2026-12-07":450,"2026-12-14":300,"2026-12-21":450,"2026-12-28":300,"2027-01-04":450,"2027-01-11":300,"2027-01-18":600,"2027-01-25":600,"2027-02-01":750,"2027-02-08":600,"2027-02-15":750,"2027-02-22":450,"2027-03-01":600,"2027-03-08":450,"2027-03-22":450,"2027-03-29":450,"2027-04-05":450,"2027-04-12":450,"2027-04-19":450,"2027-04-26":450,"2027-05-03":300,"2027-05-10":600,"2027-05-17":300,"2027-05-24":450,"2027-05-31":300,"2027-06-07":300,"2027-06-14":900,"2027-06-21":300,"2027-06-28":300,"2027-07-05":300,"2027-07-12":300,"2027-07-19":300,"2027-07-26":150,"2027-08-02":150,"2027-08-09":150,"2027-08-16":150,"2027-08-23":150,"2027-08-30":150,"2027-09-06":300,"2027-09-13":300,"2027-09-20":300}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1079","description":"Non Sterile LoPro S4","weeks":{"2026-08-24":300,"2026-08-31":300,"2026-09-14":300,"2026-09-21":300,"2026-09-28":150,"2026-10-05":300,"2026-10-19":150,"2026-10-26":150,"2026-11-02":300,"2026-11-09":150,"2026-11-16":300,"2026-11-23":150,"2026-11-30":150,"2026-12-07":150,"2026-12-14":150,"2026-12-28":300,"2027-01-04":150,"2027-01-11":150,"2027-01-18":300,"2027-01-25":300,"2027-02-01":150,"2027-02-08":300,"2027-02-22":150,"2027-03-01":150,"2027-03-15":450,"2027-03-22":450,"2027-03-29":450,"2027-04-05":450,"2027-04-12":450,"2027-04-19":450,"2027-04-26":450,"2027-05-03":300,"2027-05-17":300,"2027-05-24":150,"2027-05-31":300,"2027-06-07":600,"2027-06-21":600,"2027-06-28":300,"2027-07-05":450,"2027-07-12":450,"2027-07-19":150,"2027-07-26":150,"2027-08-02":150,"2027-08-09":150,"2027-08-16":150,"2027-08-23":150,"2027-08-30":150,"2027-09-06":150,"2027-09-13":150,"2027-09-20":150}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1151","description":"Mac S1 Eco","weeks":{"2026-10-12":300,"2026-12-28":300,"2027-03-01":150,"2027-05-03":300,"2027-08-09":150}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1152","description":"Mac S2 Eco","weeks":{"2026-08-24":300,"2026-10-05":300,"2027-01-11":450,"2027-03-15":450,"2027-05-17":300,"2027-06-28":300,"2027-08-02":300}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1137","description":"QC Miller S2","weeks":{"2026-09-28":300,"2026-12-07":300,"2027-03-08":450,"2027-05-31":300,"2027-07-19":300}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1140","description":"QC Mac S1","weeks":{"2026-08-31":300,"2026-11-23":300,"2027-02-22":300,"2027-05-24":300,"2027-07-26":300}},{"resource":"LPS4 HDMI","part_id":"VER1/0270-1154","description":"Miller S2 Eco","weeks":{"2026-09-14":300,"2027-01-04":300,"2027-02-15":150,"2027-05-10":300,"2027-08-16":300}},{"resource":"QCS4","part_id":"VER1/0270-1145","description":"QC Hyperangle S3 - NS","weeks":{"2026-08-31":1500,"2026-09-14":1500,"2026-09-28":1800,"2026-10-12":1800,"2026-10-26":1800,"2026-11-09":1500,"2026-11-23":1500,"2026-11-30":900,"2026-12-07":900,"2026-12-14":1500,"2026-12-21":1500,"2027-01-04":1500,"2027-01-18":1500,"2027-01-25":1500,"2027-02-01":1500,"2027-02-15":1500,"2027-02-22":1500,"2027-03-01":1500,"2027-03-08":1500,"2027-03-15":1500,"2027-03-22":1500,"2027-04-05":1500,"2027-04-12":1500,"2027-04-19":1500,"2027-05-03":1500,"2027-05-17":1500,"2027-05-31":1500,"2027-06-14":1500,"2027-06-28":1500,"2027-07-05":1500,"2027-07-19":1500,"2027-07-26":1500,"2027-08-02":1500,"2027-08-16":1500,"2027-08-23":1500,"2027-08-30":1500,"2027-09-06":1500,"2027-09-13":1500,"2027-09-20":1500}},{"resource":"QCS4","part_id":"VER1/0270-1084","description":"Spectrum QC HA S4","weeks":{"2026-08-24":1500,"2026-08-31":1200,"2026-09-07":2100,"2026-09-14":900,"2026-09-28":900,"2026-10-05":1500,"2026-10-12":600,"2026-10-19":2700,"2026-11-02":1500,"2026-11-09":1200,"2026-11-16":1500,"2026-11-23":1200,"2026-11-30":1800,"2026-12-07":2700,"2026-12-14":1500,"2026-12-21":1500,"2027-01-04":2700,"2027-01-11":2700,"2027-02-01":2700,"2027-02-08":2700,"2027-02-15":2700,"2027-03-01":2700,"2027-03-15":2700,"2027-03-22":2700,"2027-03-29":2700,"2027-04-12":2700,"2027-04-19":2700,"2027-05-03":2700,"2027-05-10":2700,"2027-05-24":2700,"2027-05-31":2700,"2027-06-14":2700,"2027-06-21":2700,"2027-07-05":2700,"2027-07-12":2700,"2027-07-19":1200,"2027-07-26":2700,"2027-08-02":2700,"2027-08-09":1200,"2027-08-16":1500,"2027-08-23":1500,"2027-09-06":1500,"2027-09-13":1500}},{"resource":"QCS4","part_id":"VER1/0270-1146","description":"QC Hyperangle S4 - NS","weeks":{"2026-08-24":1200,"2026-09-21":2700,"2026-10-05":1200,"2026-10-26":900,"2026-11-02":1200,"2026-11-16":1200,"2026-11-30":900,"2026-12-28":2700,"2027-01-18":2700,"2027-02-22":2700,"2027-03-08":2700,"2027-04-05":2700,"2027-04-26":2700,"2027-05-17":2700,"2027-06-07":2700,"2027-06-28":2700,"2027-07-19":1500,"2027-08-09":1500,"2027-08-30":1500,"2027-09-20":1500}},{"resource":"HDMI MIX","part_id":"VER1/0270-0876","description":"LoPro S1","weeks":{"2026-09-21":300,"2026-11-02":450,"2026-12-21":450,"2027-05-31":150,"2027-08-09":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-1075","description":"Non Sterile LoPro S1","weeks":{"2026-09-21":150,"2026-12-07":150,"2027-05-31":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-0877","description":"LoPro S2","weeks":{"2026-09-14":300,"2026-11-09":300,"2027-01-04":150,"2027-03-22":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-1076","description":"Non Sterile LoPro S2","weeks":{"2026-09-14":150,"2027-01-04":150,"2027-03-22":150,"2027-07-19":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-0962","description":"LoPro S2.5","weeks":{"2026-11-16":300,"2027-02-01":150,"2027-07-05":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-1077","description":"Non Sterile LoPro S2.5","weeks":{"2027-02-01":150,"2027-07-05":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-0932","description":"Direct View MAC S3","weeks":{"2026-09-07":450,"2026-09-21":300,"2026-10-05":300,"2026-10-12":450,"2026-10-19":450,"2026-11-02":300,"2026-12-07":450,"2026-12-14":450,"2027-01-04":300,"2027-01-25":300,"2027-02-08":300,"2027-02-22":300,"2027-03-08":300,"2027-03-15":300,"2027-03-22":150,"2027-04-05":300,"2027-04-19":300,"2027-04-26":300,"2027-06-14":300,"2027-06-28":300,"2027-07-26":300,"2027-08-09":300,"2027-08-23":300,"2027-09-13":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-1080","description":"Non Sterile DVM S3","weeks":{"2026-08-24":300,"2026-10-12":150,"2026-10-19":300,"2026-11-16":150,"2026-11-30":150,"2026-12-28":300,"2027-02-22":300,"2027-03-22":300,"2027-04-26":300,"2027-05-24":300,"2027-06-28":300,"2027-08-09":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-0933","description":"Direct View MAC S4","weeks":{"2026-08-31":450,"2026-09-28":600,"2026-11-09":300,"2026-11-30":300,"2026-12-21":300,"2026-12-28":300,"2027-01-18":300,"2027-02-15":600,"2027-03-01":600,"2027-04-12":300,"2027-05-03":300,"2027-06-07":300,"2027-08-02":300,"2027-08-30":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-1081","description":"Non Sterile DVM S4","weeks":{"2026-08-31":300,"2026-09-28":150,"2026-11-16":300,"2026-11-23":450,"2027-01-18":300,"2027-02-01":300,"2027-03-15":150,"2027-04-05":300,"2027-04-12":300,"2027-05-17":450,"2027-06-07":300,"2027-08-02":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-0967","description":"Miller 1","weeks":{"2026-09-14":300,"2026-10-26":150,"2027-01-11":300,"2027-03-29":300,"2027-07-05":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-1074","description":"Non Sterile Miller S1","weeks":{"2026-10-26":150,"2027-03-29":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-0966","description":"Miller 0","weeks":{"2026-09-07":300,"2026-10-26":300,"2026-11-23":150,"2027-01-25":300,"2027-05-10":300,"2027-08-30":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-1073","description":"Non Sterile Miller S0","weeks":{"2026-10-26":150,"2027-01-25":150,"2027-08-30":150}},{"resource":"HDMI MIX","part_id":"VER1/0270-1139","description":"QC Miller 00","weeks":{"2026-10-05":300,"2026-12-14":300,"2027-02-08":300,"2027-03-15":300,"2027-05-03":300,"2027-06-21":300,"2027-08-16":300}},{"resource":"HDMI MIX","part_id":"VER1/0270-1135","description":"QC Mac S2","weeks":{"2026-08-24":300,"2026-10-05":150,"2026-11-30":300,"2027-01-11":300,"2027-03-08":300,"2027-04-19":300,"2027-05-24":300,"2027-07-12":300,"2027-08-23":300}},{"resource":"QC MIX","part_id":"VER1/0270-1089","description":"Spectrum QC HA S1","weeks":{"2026-09-21":150,"2026-11-02":450,"2026-12-28":150,"2027-01-04":150,"2027-04-26":300,"2027-06-07":150,"2027-07-19":600}},{"resource":"QC MIX","part_id":"VER1/0270-1090","description":"Spectrum QC HA S2","weeks":{"2026-09-07":600,"2026-11-16":450,"2026-12-28":300,"2027-02-22":450,"2027-04-26":150,"2027-06-07":300,"2027-07-12":300,"2027-08-23":300}},{"resource":"QC MIX","part_id":"VER1/0270-1091","description":"SpectrumQC HA S2.5","weeks":{"2026-10-26":450,"2027-01-25":300,"2027-03-15":450,"2027-05-17":450}},{"resource":"QC MIX","part_id":"VER1/0270-1142","description":"QC Hyperangle S1 - NS","weeks":{"2026-09-21":450,"2027-01-11":450,"2027-05-31":300,"2027-07-26":150,"2027-08-23":300}},{"resource":"QC MIX","part_id":"VER1/0270-1143","description":"QC Hyperangle S2 - NS","weeks":{"2026-11-30":450,"2027-03-01":450,"2027-05-10":150,"2027-07-05":300,"2027-08-16":300}},{"resource":"QC MIX","part_id":"VER1/0270-1144","description":"QC Hyperangle S2.5 - NS","weeks":{"2026-08-24":300,"2026-12-07":450,"2027-04-12":150,"2027-05-24":300,"2027-08-09":300}},{"resource":"QC MIX","part_id":"VER1/0270-1087","description":"Spectrum QC Miller S0","weeks":{"2026-08-31":300,"2026-10-05":450,"2026-11-23":300,"2026-12-14":450,"2027-02-15":450,"2027-03-29":450,"2027-05-10":300,"2027-05-31":300,"2027-07-05":300,"2027-07-26":450,"2027-08-16":300}},{"resource":"QC MIX","part_id":"VER1/0270-1088","description":"Spectrum QC Miller S1","weeks":{"2026-08-31":300,"2026-09-28":600,"2026-11-09":450,"2027-01-04":300,"2027-01-18":300,"2027-02-08":450,"2027-03-22":450,"2027-04-19":450,"2027-05-24":150,"2027-06-28":600,"2027-08-02":600,"2027-09-06":150}},{"resource":"QC MIX","part_id":"VER1/0270-1153","description":"Miller 00 Eco","weeks":{"2026-09-14":300,"2026-11-23":150,"2027-01-18":150,"2027-01-25":150,"2027-04-05":450,"2027-08-30":300}},{"resource":"QC MIX","part_id":"VER1/0270-1149","description":"QC Miller S0 - NS","weeks":{"2026-08-24":300,"2026-10-19":450,"2026-12-21":450,"2027-02-01":150,"2027-04-12":300,"2027-05-03":150,"2027-06-14":450,"2027-07-12":300,"2027-08-30":150,"2027-09-06":300}},{"resource":"QC MIX","part_id":"VER1/0270-1150","description":"QC Miller S1  - NS","weeks":{"2026-09-14":300,"2026-10-12":600,"2027-02-01":300,"2027-03-08":450,"2027-05-03":300,"2027-06-21":600,"2027-08-09":300}},{"resource":"SU Stylet","part_id":"VER1/0270-1005","description":"Single Use Gliderite Stylet","weeks":{"2026-08-24":6000,"2026-08-31":4500,"2026-09-07":6000,"2026-09-14":6000,"2026-09-21":4500,"2026-09-28":7500,"2026-10-05":7500,"2026-10-12":6000,"2026-10-19":4500,"2026-10-26":6000,"2026-11-02":6000,"2026-11-09":6000,"2026-11-16":6000,"2026-11-23":6000,"2026-11-30":7500,"2026-12-07":6000,"2026-12-14":6000,"2026-12-21":4500,"2026-12-28":4500,"2027-01-04":7500,"2027-01-11":7500,"2027-01-18":6000,"2027-01-25":6000,"2027-02-01":6000,"2027-02-08":6000,"2027-02-15":6000,"2027-02-22":6000,"2027-03-01":6000,"2027-03-08":6000,"2027-03-15":6000,"2027-03-22":7500,"2027-03-29":7500,"2027-04-05":7500,"2027-04-12":7500,"2027-04-19":7500,"2027-04-26":6000,"2027-05-03":6000,"2027-05-10":6000,"2027-05-17":6000,"2027-05-24":6000,"2027-05-31":6000,"2027-06-07":6000,"2027-06-14":7500,"2027-06-21":6000,"2027-06-28":6000,"2027-07-05":6000,"2027-07-12":6000,"2027-07-19":6000,"2027-07-26":6000,"2027-08-02":6000,"2027-08-09":6000,"2027-08-16":6000,"2027-08-23":7500,"2027-08-30":6000,"2027-09-06":6000,"2027-09-13":6000,"2027-09-20":6000}},{"resource":"SU Stylet","part_id":"VER1/0270-1120","description":"Non Sterile Single Use Gliderite Stylet","weeks":{"2026-09-21":1500,"2026-11-23":1500,"2027-01-11":1500,"2027-03-29":1200,"2027-05-17":1500,"2027-08-02":1500}},{"resource":"SU Stylet","part_id":"VER1/0270-1093","description":"Pediatric SU Metal Stylet","weeks":{"2026-08-31":1200,"2026-10-19":1200,"2027-03-01":1200,"2027-05-24":1200,"2027-07-19":1200}},{"resource":"SU Stylet","part_id":"VER1/0270-1119","description":"Non Sterile Pediatric SU Metal Stylet","weeks":{"2026-10-19":300,"2027-05-24":300}},{"resource":"Multivac","part_id":"VER1/0270-0679","description":"GVL 0 Stat","weeks":{"2027-01-04":200,"2027-06-21":200}},{"resource":"Multivac","part_id":"VER1/0270-0428","description":"GVL 1 Stat","weeks":{"2027-01-11":200,"2027-05-24":200,"2027-08-02":200}},{"resource":"Multivac","part_id":"VER1/0270-0429","description":"GVL 2 Stat","weeks":{"2026-11-16":200,"2027-05-17":200}},{"resource":"Multivac","part_id":"VER1/0270-0709","description":"GVL 2.5 Stat","weeks":{"2026-10-19":400,"2027-05-10":200}},{"resource":"Multivac","part_id":"VER1/0270-0626","description":"GVL 3 Stat","weeks":{"2026-08-24":3600,"2026-09-21":2400,"2026-10-05":2400,"2026-11-02":2400,"2026-11-30":2400,"2026-12-14":2400,"2026-12-28":2400,"2027-01-04":2400,"2027-01-25":2400,"2027-02-22":2400,"2027-03-29":2400,"2027-04-12":2400,"2027-05-10":2400,"2027-06-07":2400,"2027-06-21":2400,"2027-07-12":2400,"2027-07-26":2400,"2027-08-23":2400}},{"resource":"Multivac","part_id":"VER1/0270-0628","description":"GVL 4 Stat","weeks":{"2026-08-31":2400,"2026-09-07":2400,"2026-09-28":2400,"2026-10-26":2400,"2026-12-21":2400,"2027-01-18":2400,"2027-02-01":2400,"2027-02-15":2400,"2027-03-01":2400,"2027-04-05":2400,"2027-04-26":2400,"2027-05-24":2400,"2027-06-28":2400,"2027-07-19":2400,"2027-08-02":2400,"2027-08-30":2400}},{"resource":"Multivac","part_id":"VER1/0270-0916","description":"Pediatric Stylet","weeks":{"2026-09-07":1000,"2026-11-02":1000,"2027-01-04":1000,"2027-03-22":1000,"2027-05-17":1000,"2027-08-23":1000}},{"resource":"Multivac","part_id":"VER1/0270-1127","description":"GS ClearFit Hyperangle 3","weeks":{"2026-09-14":1800,"2026-10-12":1800,"2026-11-09":1800,"2026-12-07":1800,"2027-01-11":1800,"2027-02-08":1800,"2027-03-08":3600,"2027-05-03":3600,"2027-06-14":3600,"2027-08-16":3600}},{"resource":"Multivac","part_id":"VER1/0270-1128","description":"GS ClearFit Hyperangle 4","weeks":{"2026-08-24":200,"2026-09-14":1200,"2026-10-12":1200,"2026-11-09":1800,"2026-12-07":1800,"2027-01-11":1800,"2027-02-08":1800,"2027-03-22":1800,"2027-04-19":1800,"2027-05-31":3600,"2027-07-05":1800,"2027-08-09":3600}},{"resource":"Multivac","part_id":"VER1/0270-1129","description":"GS ClearFit MAC 2","weeks":{"2026-11-09":200,"2027-03-15":400,"2027-08-09":200}},{"resource":"Multivac","part_id":"VER1/0270-1130","description":"GS ClearFit MAC 3","weeks":{"2026-08-31":600,"2026-10-19":600,"2026-11-30":600,"2027-01-18":600,"2027-03-15":1200,"2027-05-17":1200,"2027-08-09":600}},{"resource":"Multivac","part_id":"VER1/0270-1131","description":"GS ClearFit MAC 4","weeks":{"2026-08-31":600,"2026-10-12":600,"2026-12-07":600,"2027-02-15":600,"2027-04-05":600,"2027-05-31":600,"2027-07-19":600,"2027-08-30":600}},{"resource":"Multivac","part_id":"VER1/0270-1132","description":"GS ClearFit Miller 2","weeks":{"2026-10-19":200,"2027-04-05":200,"2027-07-19":200}},{"resource":"Multivac","part_id":"VER1/0270-1121","description":"Non Sterile GVL 0","weeks":{"2027-01-04":100}},{"resource":"Multivac","part_id":"VER1/0270-1125","description":"Non Sterile GVL 3 Stat","weeks":{"2026-11-30":600,"2027-04-19":600,"2027-07-05":600}},{"resource":"Multivac","part_id":"VER1/0270-1126","description":"Non Sterile GVL 4 Stat","weeks":{"2026-10-26":600,"2026-12-07":600,"2027-03-15":600,"2027-05-17":600,"2027-07-05":600}},{"resource":"Multivac","part_id":"VER1/0270-1118","description":"Non Sterile Gliderite Stylet, Pediatric","weeks":{"2026-09-07":200,"2027-01-04":200,"2027-05-17":200,"2027-08-23":200}},{"resource":"RU Stylet","part_id":"VER1/0270-0681","description":"RU Stylet","weeks":{"2026-08-24":600,"2026-09-07":600,"2026-09-28":600,"2026-10-19":600,"2026-11-09":600,"2026-11-30":600,"2026-12-07":600,"2027-01-11":600,"2027-02-01":600,"2027-02-22":600,"2027-03-15":600,"2027-04-05":600,"2027-04-26":600,"2027-05-17":600,"2027-06-07":600,"2027-06-28":600,"2027-07-19":600,"2027-08-09":600,"2027-08-30":600,"2027-09-20":600}},{"resource":"Titanium","part_id":"VER1/0143-0001","description":"Ti, LoPro T2","weeks":{"2026-11-23":48}},{"resource":"Titanium","part_id":"VER1/0143-0002","description":"Ti, LoPro T3","weeks":{"2026-08-31":38,"2026-09-21":32,"2026-10-05":48,"2026-10-26":24,"2026-11-02":48,"2026-11-09":48,"2026-12-07":48}},{"resource":"Titanium","part_id":"VER1/0143-0003","description":"Ti, LoPro T4","weeks":{"2026-08-24":48,"2026-09-14":48,"2026-09-21":16,"2026-09-28":48,"2026-10-12":48,"2026-11-16":48,"2026-11-30":48,"2026-12-14":48}},{"resource":"Titanium","part_id":"VER1/0143-0004","description":"Ti, MAC T3","weeks":{"2026-09-07":24,"2026-10-26":24}},{"resource":"Titanium","part_id":"VER1/0143-0005","description":"Ti, MAC T4","weeks":{"2026-09-07":24,"2026-10-19":48}},{"resource":"ORION","part_id":"VER1/0122-1305","description":"Left Handle Shell, Orion","weeks":{"2026-08-24":10800}},{"resource":"ORION","part_id":"VER1/0122-1306","description":"Right Handle Shell, Orion","weeks":{"2026-08-24":6180,"2026-09-14":4620}},{"resource":"ORION","part_id":"VER1/0122-1320","description":"Compression Coil Stop, Standard Direction, Orion","weeks":{"2026-08-24":12000}},{"resource":"ORION","part_id":"VER1/0122-1321","description":"Compression Coil Stop, REVERSE Direction, Orion","weeks":{"2026-09-14":6000}},{"resource":"ORION","part_id":"VER1/0122-1322","description":"Funnel, Protective Cover, Orion","weeks":{"2026-08-31":6000,"2026-10-19":10000}},{"resource":"ORION","part_id":"VER1/0122-1379","description":"Handle Protective Cover","weeks":{"2026-08-31":12000}},{"resource":"BFlex Sampler","part_id":"VER1/0270-1141","description":"SAMPLER, BFLEX, GS22146","weeks":{"2026-08-31":700,"2026-09-28":980,"2026-10-26":980,"2026-11-30":980,"2027-01-11":980,"2027-02-08":1120}},{"resource":"BFlex","part_id":"VER1/0143-0007","description":"Shell, Left, SMI, BFlex 2, GS22130","weeks":{"2026-08-24":10000,"2026-08-31":20000,"2026-09-07":10000,"2026-09-14":20000,"2026-09-21":20000,"2026-09-28":20000,"2026-10-05":10000,"2026-10-12":20000,"2026-10-19":10000,"2026-10-26":20000,"2026-11-02":20000,"2026-11-09":20000,"2026-11-16":20000,"2026-11-23":20000,"2026-11-30":20000,"2026-12-07":20000,"2026-12-14":10000,"2026-12-21":20000,"2026-12-28":20000,"2027-01-04":10000,"2027-01-11":20000,"2027-01-18":10000}},{"resource":"BFlex","part_id":"VER1/0143-0008","description":"Shell, Right, SMI, BFlex 2, GS22130","weeks":{"2026-08-24":15000,"2026-08-31":20000,"2026-09-07":10000,"2026-09-14":20000,"2026-09-21":20000,"2026-09-28":20000,"2026-10-05":10000,"2026-10-12":20000,"2026-10-19":10000,"2026-10-26":20000,"2026-11-02":20000,"2026-11-09":20000,"2026-11-16":20000,"2026-11-23":20000,"2026-11-30":20000,"2026-12-07":10000,"2026-12-14":20000,"2026-12-21":20000,"2026-12-28":10000,"2027-01-04":20000,"2027-01-11":10000,"2027-01-18":20000}}];

function parseXlsm(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      try {
        const data = new Uint8Array(e.target.result);
        const wb = XLSX.read(data, { type:'array', cellDates:true });
        const ws = wb.Sheets['SMI TRACKER'];
        if (!ws) return reject(new Error("Sheet 'SMI TRACKER' not found"));
        const rows = XLSX.utils.sheet_to_json(ws, { header:1, raw:false, dateNF:'yyyy-mm-dd' });
        const headerRow = rows[4] || [];
        const weekCols = [];
        for (let i = 9; i < headerRow.length; i++) {
          const v = headerRow[i];
          if (v && /^\d{4}-\d{2}-\d{2}/.test(String(v).trim()))
            weekCols.push({ idx:i, label:String(v).trim().slice(0,10) });
        }
        const results = [];
        let currentResource = null;
        for (let r = 5; r < rows.length; r++) {
          const row = rows[r];
          const resourceLabel = row[2];
          const partId = row[3], desc = row[4], rowType = row[8];
          if (resourceLabel && String(resourceLabel).trim()) currentResource = String(resourceLabel).trim();
          if (rowType === 'Build Plan' && row[0] && partId) {
            const weeks = {};
            for (const { idx, label } of weekCols) {
              const qty = parseFloat(row[idx]);
              if (!isNaN(qty) && qty !== 0) weeks[label] = Math.round(qty);
            }
            if (Object.keys(weeks).length > 0)
              results.push({ resource: currentResource || String(row[0]).trim(), part_id: String(partId).trim(), description: desc ? String(desc).trim() : '', weeks });
          }
        }
        resolve(results);
      } catch(err) { reject(err); }
    };
    reader.onerror = () => reject(new Error('File read error'));
    reader.readAsArrayBuffer(file);
  });
}

function fmtWeek(d) { const dt = new Date(d+'T00:00:00'); return dt.toLocaleDateString('en-US',{month:'short',day:'numeric'}); }
function fmtQty(n) { return n >= 1000 ? n.toLocaleString() : String(n); }

const RESOURCE_COLORS = ['#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af','#1e40af'];
function resourceColor(resource, allResources) {
  const idx = allResources.indexOf(resource);
  return RESOURCE_COLORS[idx % RESOURCE_COLORS.length];
}

function App() {
  const [data, setData] = useState(INITIAL_DATA);
  const [dataDate, setDataDate] = useState('Aug 24, 2026');
  const [uploading, setUploading] = useState(false);
  const [actuals, setActuals] = useState({}); // { "part_id": { "2026-08-24": qty, ... } }
  const [actualsLoading, setActualsLoading] = useState(true);

  // Load actuals from Firestore on mount
  useEffect(() => {
    const DOC_REF = db.collection('production_data').doc('ver_actuals');
    DOC_REF.get().then(snap => {
      if (!snap.exists) { console.warn('[VERBuildPlan] production_data/latest does not exist'); setActualsLoading(false); return; }
      const d = snap.data();
      const rows = d.rows || [];
      console.log('[VERBuildPlan] Firestore rows loaded:', rows.length);
      // Sample first few rows to debug
      const sample = rows.slice(0, 3);
      console.log('[VERBuildPlan] Sample rows:', JSON.stringify(sample));
      const woRows = rows.filter(r => r.part_id && r.part_id.trim());
      console.log('[VERBuildPlan] Rows with part_id field:', woRows.length, 'of', rows.length);
      const map = {};
      rows.forEach(r => {
        const wo = (r.part_id || '').trim();
        const qty = parseFloat(r.qty) || 0;
        const date = r.date || '';
        if (!wo || !date || qty <= 0) return;
        const week = toMonday(date);
        if (!map[wo]) map[wo] = {};
        map[wo][week] = (map[wo][week] || 0) + qty;
      });
      console.log('[VERBuildPlan] Unique part_ids with actuals:', Object.keys(map).length);
      console.log('[VERBuildPlan] Sample part_id keys:', Object.keys(map).slice(0, 5));
      setActuals(map);
      setActualsLoading(false);
    }).catch(err => { console.error('[VERBuildPlan] Firestore error:', err); setActualsLoading(false); });
  }, []);
  const [uploadError, setUploadError] = useState('');
  const [search, setSearch] = useState('');
  const [selectedWeek, setSelectedWeek] = useState('');
  const [selectedResources, setSelectedResources] = useState(new Set());
  const [viewMode, setViewMode] = useState('week');

  const today = new Date().toISOString().slice(0,10);

  const allResources = useMemo(() => ['All', ...Array.from(new Set(data.map(r => r.resource)))], [data]);

  const allWeeks = useMemo(() => {
    const s = new Set(); data.forEach(r => Object.keys(r.weeks).forEach(w => s.add(w)));
    return Array.from(s).sort();
  }, [data]);

  const defaultWeek = useMemo(() => {
    const thisMonday = toMonday(today);
    // If this Monday exists in allWeeks, use it; otherwise find closest past week
    if (allWeeks.includes(thisMonday)) return thisMonday;
    // Fall back to most recent week that is <= today
    const past = allWeeks.filter(w => w <= today);
    return past.length > 0 ? past[past.length - 1] : (allWeeks[0] || '');
  }, [allWeeks, today]);
  const currentWeek = selectedWeek || defaultWeek;

  const filtered = useMemo(() => {
    const q = search.toLowerCase();
    return data.filter(r =>
      (selectedResources.size === 0 || selectedResources.has(r.resource)) &&
      (!q || r.resource.toLowerCase().includes(q) || r.part_id.toLowerCase().includes(q) || r.description.toLowerCase().includes(q))
    );
  }, [data, search, selectedResources]);

  const weekRows = useMemo(() => filtered.filter(r => r.weeks[currentWeek] != null), [filtered, currentWeek]);
  const visibleWeeks = useMemo(() => allWeeks.filter(w => w >= today).slice(0, 8), [allWeeks, today]);

  const handleUpload = useCallback(async (file) => {
    if (!file) return;
    setUploading(true); setUploadError('');
    try {
      const parsed = await parseXlsm(file);
      if (parsed.length === 0) throw new Error('No Build Plan rows found.');
      setData(parsed);
      setDataDate(new Date().toLocaleDateString('en-US',{month:'short',day:'numeric',year:'numeric'}));
      setSelectedWeek(''); setSelectedResources(new Set());
    } catch(err) { setUploadError(err.message || 'Failed to parse file.'); }
    finally { setUploading(false); }
  }, []);

  const onFileInput = useCallback(e => { const f = e.target.files[0]; if(f) handleUpload(f); e.target.value=''; }, [handleUpload]);
  const onDrop = useCallback(e => { e.preventDefault(); const f = e.dataTransfer.files[0]; if(f) handleUpload(f); }, [handleUpload]);

  const s = (obj) => Object.assign({}, obj); // style helper

  return (
    <div style={{minHeight:'100vh',background:'#f8fafc',color:'#0f172a',display:'flex',flexDirection:'column'}}>
      {/* Header */}
      <div style={{background:'#ffffff',borderBottom:'1px solid #e2e8f0',padding:'14px 20px',display:'flex',alignItems:'center',justifyContent:'space-between',flexWrap:'wrap',gap:10}}>
        <div>
          <div style={{fontSize:17,fontWeight:700,color:'#0f172a'}}>VER Weekly Plan</div>
          <div style={{fontSize:11,color:'#94a3b8',marginTop:2}}>Data as of {dataDate} · {data.length} parts · {allResources.length-1} resources</div>
        </div>
        <label style={{display:'flex',alignItems:'center',gap:6,cursor:'pointer',background:'#2563eb',color:'#ffffff',fontSize:13,fontWeight:500,padding:'7px 14px',borderRadius:7}}
          onDragOver={e=>e.preventDefault()} onDrop={onDrop}>
          {uploading ? 'Parsing…' : '⬆ Update File'}
          <input type="file" accept=".xlsm,.xlsx" style={{display:'none'}} onChange={onFileInput}/>
        </label>
      </div>

      {uploadError && <div style={{background:'#fee2e2',borderBottom:'1px solid #fca5a5',color:'#991b1b',padding:'8px 20px',fontSize:13}}>⚠ {uploadError}</div>}

      {/* Resource filter bar */}
      <div style={{background:'#f1f5f9',borderBottom:'1px solid #e2e8f0',padding:'8px 20px',overflowX:'auto'}}>
        <div style={{display:'flex',gap:6,alignItems:'center',minWidth:'max-content'}}>
          <span style={{fontSize:11,color:'#94a3b8',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.05em',marginRight:4,flexShrink:0}}>Resource:</span>
          {allResources.map(res => {
            const isAll = res === 'All';
            const active = isAll ? selectedResources.size === 0 : selectedResources.has(res);
            const color = isAll ? '#64748b' : '#1e40af';
            const handleClick = () => {
              if (isAll) { setSelectedResources(new Set()); return; }
              setSelectedResources(prev => {
                const next = new Set(prev);
                if (next.has(res)) next.delete(res); else next.add(res);
                return next;
              });
            };
            return (
              <button key={res} onClick={handleClick}
                style={{padding:'4px 12px',borderRadius:20,fontSize:12,fontWeight:active?600:400,cursor:'pointer',border:`1px solid ${active ? color : '#cbd5e1'}`,
                  background: active ? color + '22' : 'transparent',
                  color: active ? color : '#64748b', transition:'all 0.15s', flexShrink:0}}>
                {res}
              </button>
            );
          })}
          {selectedResources.size > 0 && (
            <button onClick={() => setSelectedResources(new Set())}
              style={{padding:'4px 10px',borderRadius:20,fontSize:11,cursor:'pointer',border:'1px solid #fca5a5',background:'#fee2e2',color:'#dc2626',flexShrink:0,marginLeft:4}}>
              ✕ Clear
            </button>
          )}
        </div>
      </div>

      {/* Controls */}
      <div style={{background:'#f8fafc',borderBottom:'1px solid #e2e8f0',padding:'8px 20px',display:'flex',alignItems:'center',gap:10,flexWrap:'wrap'}}>
        <input type="text" placeholder="Search part, description…" value={search} onChange={e=>setSearch(e.target.value)}
          style={{flex:1,minWidth:180,background:'#e2e8f0',border:'1px solid #cbd5e1',borderRadius:7,padding:'7px 12px',fontSize:13,color:'#0f172a',outline:'none'}}/>
        <div style={{display:'flex',borderRadius:7,overflow:'hidden',border:'1px solid #cbd5e1',flexShrink:0}}>
          {[['week','Week View'],['table','Multi-Week'],['avg','Avg / Resource'],['camera','By Camera']].map(([m,label]) => (
            <button key={m} onClick={()=>setViewMode(m)}
              style={{padding:'7px 14px',fontSize:13,fontWeight:500,cursor:'pointer',border:'none',background:viewMode===m?'#2563eb':'#e2e8f0',color:viewMode===m?'#fff':'#64748b'}}>
              {label}
            </button>
          ))}
        </div>
      </div>

      {/* Week selector */}
      {viewMode === 'week' && (
        <div style={{background:'#f1f5f9',borderBottom:'1px solid #e2e8f0',padding:'8px 20px',overflowX:'auto'}}>
          <div style={{display:'flex',alignItems:'center',gap:6,minWidth:'max-content'}}>
            <span style={{fontSize:11,color:'#94a3b8',fontWeight:600,textTransform:'uppercase',letterSpacing:'0.05em',marginRight:4,flexShrink:0}}>Week:</span>
            {allWeeks.map(w => (
              <button key={w} onClick={()=>setSelectedWeek(w)}
                style={{fontSize:12,padding:'4px 11px',borderRadius:20,cursor:'pointer',border:'1px solid',flexShrink:0,
                  background: w===currentWeek?'#2563eb': '#ffffff',
                  borderColor: w===currentWeek?'#3b82f6': w===defaultWeek?'#1e3a5f':'#cbd5e1',
                  color: w===currentWeek?'#fff': w===defaultWeek?'#93c5fd':'#94a3b8',
                  fontWeight: w===currentWeek?600:400}}>
                {fmtWeek(w)}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Content */}
      <div style={{flex:1,overflow:'auto',padding:20}}>
        {viewMode === 'week'
          ? <WeekView rows={weekRows} week={currentWeek} allResources={allResources.slice(1)} actuals={actuals} actualsLoading={actualsLoading} />
          : viewMode === 'avg'
          ? <AvgView rows={filtered} weeks={visibleWeeks} allResources={allResources.slice(1)} />
          : viewMode === 'camera'
          ? <CameraView rows={filtered} weeks={visibleWeeks} allWeeks={allWeeks} />
          : <TableView rows={filtered} weeks={visibleWeeks} allWeeks={allWeeks} allResources={allResources.slice(1)} />}
      </div>
    </div>
  );
}

function WeekView({ rows, week, allResources, actuals, actualsLoading }) {
  const [collapsedCards, setCollapsedCards] = useState(new Set());

  const toggleCard = (res) => setCollapsedCards(prev => {
    const next = new Set(prev);
    if (next.has(res)) next.delete(res); else next.add(res);
    return next;
  });

  if (!week) return <div style={{textAlign:'center',color:'#94a3b8',paddingTop:60}}>No data loaded.</div>;
  if (rows.length === 0) return <div style={{textAlign:'center',color:'#94a3b8',paddingTop:60}}>No build plan for week of {fmtWeek(week)}.</div>;
  const total = rows.reduce((s,r) => s+(r.weeks[week]||0), 0);

  const groups = [];
  const seen = {};
  rows.forEach(r => {
    if (!seen[r.resource]) { seen[r.resource] = []; groups.push(r.resource); }
    seen[r.resource].push(r);
  });

  const allAreCollapsed = groups.length > 0 && groups.every(r => collapsedCards.has(r));
  const toggleAll = () => {
    if (allAreCollapsed) setCollapsedCards(new Set());
    else setCollapsedCards(new Set(groups));
  };

  return (
    <div>
      <div style={{color:'#64748b',fontSize:13,marginBottom:14,display:'flex',alignItems:'center',gap:16,flexWrap:'wrap'}}>
        <span><span style={{color:'#0f172a',fontWeight:600}}>{rows.length}</span> parts · <span style={{color:'#0f172a',fontWeight:600}}>{total.toLocaleString()}</span> planned units</span>
        {actualsLoading
          ? <span style={{color:'#94a3b8',fontSize:12}}>⏳ Loading actuals…</span>
          : <span style={{color:'#64748b',fontSize:12}}>● Actuals from labour tickets</span>}
        <button onClick={toggleAll} style={{marginLeft:'auto',fontSize:12,color:'#1e40af',background:'transparent',border:'1px solid #c4d4e8',borderRadius:7,padding:'4px 12px',cursor:'pointer',fontWeight:500}}>
          {allAreCollapsed ? '▸ Expand All' : '▾ Collapse All'}
        </button>
      </div>
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fit,minmax(320px,1fr))',gap:16}}>
      {groups.map(res => {
        const parts = seen[res];
        const resPlanned = parts.reduce((s,r)=>s+(r.weeks[week]||0),0);
        const resActual = parts.reduce((s,r)=>s+((actuals[r.part_id]||{})[week]||0),0);
        const resPct = resPlanned > 0 ? Math.min(100, Math.round(resActual/resPlanned*100)) : 0;
        const color = '#1e40af';
        const barColor = resPct>=100?'#16a34a': resPct>=50?'#f59e0b':color;
        const collapsed = collapsedCards.has(res);
        return (
          <div key={res} style={{background:'#d8e4f0',border:'1px solid #c4d4e8',borderRadius:12,padding:'16px',display:'flex',flexDirection:'column',gap:10}}>
            {/* Resource header - clickable to collapse */}
            <div onClick={()=>toggleCard(res)} style={{cursor:'pointer'}}>
              <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:8,marginBottom:6}}>
                <span style={{fontSize:16,fontWeight:800,color:'#0f172a',letterSpacing:'-0.3px'}}>{res}</span>
                <div style={{display:'flex',alignItems:'center',gap:8,flexShrink:0}}>
                  {!actualsLoading && resPlanned > 0 && (
                    <span style={{fontSize:14,fontWeight:800,color:barColor}}>{resPct}%</span>
                  )}
                  <span style={{fontSize:14,color:'#94a3b8',lineHeight:1}}>{collapsed ? '▸' : '▾'}</span>
                </div>
              </div>
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginBottom:8}}>
                <div>
                  <span style={{fontSize:11,color:'#64748b'}}>{parts.length} part{parts.length>1?'s':''} · </span>
                  <span style={{fontSize:13,fontWeight:700,color:'#0f172a'}}>{resPlanned.toLocaleString()}</span>
                  <span style={{fontSize:11,color:'#64748b'}}> planned</span>
                </div>
                {!actualsLoading && resPlanned > 0 && (
                  <div style={{textAlign:'right'}}>
                    <span style={{fontSize:20,fontWeight:800,color:barColor}}>{resActual.toLocaleString()}</span>
                    <span style={{fontSize:11,color:'#64748b',marginLeft:4}}>actual</span>
                  </div>
                )}
              </div>
              {!actualsLoading && resPlanned > 0 && (
                <div style={{height:10,background:'#b8cfe0',borderRadius:6,overflow:'hidden'}}>
                  <div style={{height:'100%',width:resPct+'%',background:barColor,borderRadius:6}}/>
                </div>
              )}
            </div>
            {/* Parts - hidden when collapsed */}
            {!collapsed && (
            <div style={{display:'flex',flexDirection:'column',gap:6}}>
              {parts.map(r => {
                const planned = r.weeks[week] || 0;
                const actual = ((actuals[r.part_id]||{})[week]||0);
                const pct = planned > 0 ? Math.min(100, Math.round(actual/planned*100)) : 0;
                const pBarColor = pct>=100?'#16a34a': pct>=50?'#f59e0b':'#1e40af';
                return (
                  <div key={r.part_id} style={{background:'#eef3f8',borderRadius:8,padding:'10px 12px'}}>
                    <div style={{display:'flex',alignItems:'flex-start',justifyContent:'space-between',gap:8,marginBottom:!actualsLoading&&planned>0?7:0}}>
                      <div style={{minWidth:0}}>
                        <div style={{color:'#1e293b',fontWeight:600,fontSize:12,lineHeight:1.3}}>{r.description||r.part_id}</div>
                        <div style={{color:'#cbd5e1',fontSize:10,marginTop:2}}>{r.part_id}</div>
                      </div>
                      <div style={{display:'flex',alignItems:'center',gap:10,flexShrink:0}}>
                        {!actualsLoading && planned > 0 && (
                          <div style={{textAlign:'right'}}>
                            <div style={{fontSize:12,fontWeight:700,color:pBarColor}}>{actual.toLocaleString()}</div>
                            <div style={{color:'#94a3b8',fontSize:9}}>actual</div>
                          </div>
                        )}
                        <div style={{textAlign:'right'}}>
                          <div style={{fontSize:18,fontWeight:800,color:'#0f172a'}}>{fmtQty(planned)}</div>
                          <div style={{color:'#94a3b8',fontSize:9}}>planned</div>
                        </div>
                      </div>
                    </div>
                    {!actualsLoading && planned > 0 && (
                      <>
                        <div style={{height:4,background:'#e2e8f0',borderRadius:4,overflow:'hidden'}}>
                          <div style={{height:'100%',width:pct+'%',background:pBarColor,borderRadius:4}}/>
                        </div>
                        <div style={{display:'flex',justifyContent:'space-between',marginTop:3}}>
                          <span style={{fontSize:9,color:'#94a3b8'}}>{pct}% complete</span>
                          {actual >= planned && <span style={{fontSize:9,color:'#16a34a',fontWeight:700}}>✓ Done</span>}
                          {actual > 0 && planned - actual > 0 && <span style={{fontSize:9,color:'#94a3b8'}}>{(planned-actual).toLocaleString()} left</span>}
                        </div>
                      </>
                    )}
                  </div>
                );
              })}
            </div>
            )}
          </div>
        );
      })}
      </div>
    </div>
  );
}

function TableView({ rows, weeks, allWeeks, allResources }) {
  const [showAll, setShowAll] = useState(false);
  const displayWeeks = showAll ? allWeeks : weeks;
  if (rows.length === 0) return <div style={{textAlign:'center',color:'#94a3b8',paddingTop:60}}>No results.</div>;

  // Group rows by resource
  const groups = [];
  const seen = {};
  rows.forEach(r => {
    if (!seen[r.resource]) { seen[r.resource] = []; groups.push(r.resource); }
    seen[r.resource].push(r);
  });

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:10,flexWrap:'wrap',gap:8}}>
        <div style={{color:'#94a3b8',fontSize:13}}>
          <span style={{color:'#0f172a',fontWeight:600}}>{rows.length}</span> parts · <span style={{color:'#0f172a',fontWeight:600}}>{displayWeeks.length}</span> weeks
        </div>
        <button onClick={()=>setShowAll(v=>!v)} style={{fontSize:12,color:'#2563eb',background:'transparent',border:'1px solid #cbd5e1',borderRadius:7,padding:'5px 12px',cursor:'pointer'}}>
          {showAll ? 'Show near-term only' : `Show all ${allWeeks.length} weeks`}
        </button>
      </div>
      <div style={{overflowX:'auto',borderRadius:10,border:'1px solid #e2e8f0'}}>
        <table style={{minWidth:'100%',borderCollapse:'collapse',fontSize:12}}>
          <thead>
            <tr style={{background:'#f1f5f9',color:'#94a3b8',fontSize:11,textTransform:'uppercase',letterSpacing:'0.05em'}}>
              <th style={{position:'sticky',left:0,zIndex:10,background:'#f1f5f9',padding:'9px 14px',textAlign:'left',borderBottom:'1px solid #e2e8f0',borderRight:'1px solid #e2e8f0',minWidth:170,whiteSpace:'nowrap'}}>Resource / Part</th>
              {displayWeeks.map(w => <th key={w} style={{padding:'9px 10px',textAlign:'center',borderBottom:'1px solid #e2e8f0',minWidth:68,whiteSpace:'nowrap'}}>{fmtWeek(w)}</th>)}
            </tr>
          </thead>
          <tbody>
            {groups.map(res => {
              const parts = seen[res];
              const color = resourceColor(res, allResources);
              const resRows = displayWeeks.map(w => parts.reduce((s,r)=>s+(r.weeks[w]||0),0));
              return (
                <React.Fragment key={res}>
                  {/* Resource subtotal row */}
                  <tr style={{background:'#f1f5f9'}}>
                    <td style={{position:'sticky',left:0,zIndex:5,background:'#f1f5f9',padding:'7px 14px',borderRight:'1px solid #e2e8f0',borderBottom:'1px solid #cbd5e1'}}>
                      <div style={{display:'flex',alignItems:'center',gap:8}}>
                        <div style={{width:3,height:16,borderRadius:2,background:color,flexShrink:0}}/>
                        <span style={{color,fontWeight:700,fontSize:12}}>{res}</span>
                        <span style={{color:'#64748b',fontSize:11}}>({parts.length})</span>
                      </div>
                    </td>
                    {resRows.map((total,i) => (
                      <td key={i} style={{padding:'7px 10px',textAlign:'center',borderBottom:'1px solid #cbd5e1',whiteSpace:'nowrap'}}>
                        {total > 0 ? <span style={{color,fontWeight:700,fontSize:12}}>{fmtQty(total)}</span> : <span style={{color:'#cbd5e1'}}>—</span>}
                      </td>
                    ))}
                  </tr>
                  {/* Part rows */}
                  {parts.map((r,i) => (
                    <tr key={r.part_id} style={{background: i%2===0 ? '#ffffff' : '#f8fafc', borderBottom:'1px solid #e2e8f0'}}>
                      <td style={{position:'sticky',left:0,zIndex:5,background: i%2===0?'#ffffff':'#f8fafc',padding:'8px 14px 8px 24px',borderRight:'1px solid #e2e8f0',minWidth:170}}>
                        <div style={{color:'#1e293b',fontWeight:500,fontSize:12,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:155}}>{r.description||r.part_id}</div>
                        <div style={{color:'#cbd5e1',fontSize:10,marginTop:1,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{r.part_id}</div>
                      </td>
                      {displayWeeks.map(w => {
                        const qty = r.weeks[w];
                        return (
                          <td key={w} style={{padding:'8px 10px',textAlign:'center',whiteSpace:'nowrap'}}>
                            {qty != null ? <span style={{color:'#1d4ed8',fontWeight:600}}>{fmtQty(qty)}</span> : <span style={{color:'#cbd5e1'}}>—</span>}
                          </td>
                        );
                      })}
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function AvgView({ rows, weeks, allResources }) {
  if (rows.length === 0) return <div style={{textAlign:'center',color:'#94a3b8',paddingTop:60}}>No results.</div>;

  // Build per-resource stats across the next 8 weeks
  const resources = [];
  const seen = {};
  rows.forEach(r => {
    if (!seen[r.resource]) { seen[r.resource] = []; resources.push(r.resource); }
    seen[r.resource].push(r);
  });

  const resourceStats = resources.map(res => {
    const parts = seen[res];
    // For each week, sum all parts in this resource
    const weekTotals = weeks.map(w => parts.reduce((s, r) => s + (r.weeks[w] || 0), 0));
    const activeWeeks = weekTotals.filter(v => v > 0);
    const totalUnits = weekTotals.reduce((s, v) => s + v, 0);
    const avg = activeWeeks.length > 0 ? Math.round(totalUnits / weeks.length) : 0; // avg over all 8 weeks (incl. zeros)
    const avgActive = activeWeeks.length > 0 ? Math.round(totalUnits / activeWeeks.length) : 0;
    const maxWeek = weeks[weekTotals.indexOf(Math.max(...weekTotals))];
    const maxVal = Math.max(...weekTotals);
    return { res, parts, weekTotals, totalUnits, avg, avgActive, activeWeeks: activeWeeks.length, maxWeek, maxVal };
  });

  const globalMax = Math.max(...resourceStats.map(s => s.avg));

  return (
    <div>
      <div style={{color:'#94a3b8',fontSize:13,marginBottom:16}}>
        Average weekly build plan per resource · next <span style={{color:'#0f172a',fontWeight:600}}>{weeks.length}</span> weeks
        ({weeks.length > 0 ? fmtWeek(weeks[0]) + ' – ' + fmtWeek(weeks[weeks.length-1]) : '—'})
      </div>
      <div style={{display:'grid',gap:10}}>
        {resourceStats.sort((a,b) => b.avg - a.avg).map(({ res, parts, weekTotals, totalUnits, avg, avgActive, activeWeeks, maxWeek, maxVal }) => {
          const color = resourceColor(res, allResources);
          const barPct = globalMax > 0 ? (avg / globalMax) * 100 : 0;
          return (
            <div key={res} style={{background:'#ffffff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
              {/* Top row */}
              <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',gap:12,marginBottom:10}}>
                <div style={{display:'flex',alignItems:'center',gap:8,minWidth:0}}>
                  <div style={{width:4,height:20,borderRadius:2,background:color,flexShrink:0}}/>
                  <span style={{color,fontWeight:700,fontSize:14}}>{res}</span>
                  <span style={{color:'#64748b',fontSize:12,marginLeft:2}}>{parts.length} part{parts.length>1?'s':''}</span>
                </div>
                <div style={{display:'flex',gap:20,flexShrink:0}}>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontSize:24,fontWeight:800,color}}>{avg > 0 ? fmtQty(avg) : '—'}</div>
                    <div style={{fontSize:10,color:'#94a3b8',marginTop:1}}>avg / week (all 8)</div>
                  </div>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontSize:18,fontWeight:600,color:'#1e293b'}}>{avgActive > 0 ? fmtQty(avgActive) : '—'}</div>
                    <div style={{fontSize:10,color:'#94a3b8',marginTop:1}}>avg on active weeks</div>
                  </div>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontSize:16,fontWeight:600,color:'#64748b'}}>{fmtQty(totalUnits)}</div>
                    <div style={{fontSize:10,color:'#94a3b8',marginTop:1}}>total 8 weeks</div>
                  </div>
                </div>
              </div>

              {/* Bar */}
              <div style={{background:'#e2e8f0',borderRadius:4,height:6,marginBottom:10,overflow:'hidden'}}>
                <div style={{width:barPct+'%',height:'100%',background:color,borderRadius:4,transition:'width 0.3s'}}/>
              </div>

              {/* Per-week breakdown */}
              <div style={{display:'flex',gap:4,flexWrap:'wrap'}}>
                {weeks.map((w, i) => {
                  const val = weekTotals[i];
                  const isMax = val === maxVal && val > 0;
                  return (
                    <div key={w} style={{flex:'1 1 60px',minWidth:56,background: val > 0 ? color+'18' : '#f8fafc',border:`1px solid ${val > 0 ? color+'44' : '#e2e8f0'}`,
                      borderRadius:7,padding:'6px 8px',textAlign:'center'}}>
                      <div style={{fontSize:10,color:'#94a3b8',marginBottom:3}}>{fmtWeek(w)}</div>
                      <div style={{fontSize:13,fontWeight:val>0?700:400,color: isMax ? color : val>0 ? '#1e293b' : '#cbd5e1'}}>
                        {val > 0 ? fmtQty(val) : '—'}
                      </div>
                    </div>
                  );
                })}
              </div>

              {/* Active weeks note */}
              {activeWeeks < weeks.length && (
                <div style={{marginTop:8,fontSize:11,color:'#94a3b8'}}>
                  Active {activeWeeks}/{weeks.length} weeks · peak {maxVal > 0 ? fmtQty(maxVal) + ' on ' + fmtWeek(maxWeek) : '—'}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

const CAMERA_MAP = {"VER1/0270-0938":"HDMI","VER1/0270-1078":"HDMI","VER1/0270-1083":"QC","VER1/0270-0939":"HDMI","VER1/0270-1079":"HDMI","VER1/0270-1145":"QC Green","VER1/0270-1084":"QC","VER1/0270-1146":"QC Green","VER1/0270-0876":"HDMI","VER1/0270-0877":"HDMI","VER1/0270-0962":"HDMI","VER1/0270-0932":"HDMI","VER1/0270-0933":"HDMI","VER1/0270-0966":"Miller HDMI","VER1/0270-1075":"HDMI","VER1/0270-1076":"HDMI","VER1/0270-1077":"HDMI","VER1/0270-1080":"HDMI","VER1/0270-1081":"HDMI","VER1/0270-1073":"Miller HDMI","VER1/0270-1089":"QC","VER1/0270-1090":"QC","VER1/0270-1091":"QC","VER1/0270-1085":"QC","VER1/0270-1086":"QC","VER1/0270-1142":"QC Green","VER1/0270-1143":"QC Green","VER1/0270-1144":"QC Green","VER1/0270-1147":"QC Green","VER1/0270-1148":"QC Green","VER1/0270-1087":"Miller QC","VER1/0270-1088":"Miller QC","VER1/0270-0967":"Miller HDMI","VER1/0270-1149":"Miller QC Green","VER1/0270-1150":"Miller QC Green","VER1/0270-1074":"Miller HDMI","VER1/0270-1137":"QC","VER1/0270-1139":"Miller QC","VER1/0270-1140":"Miller QC","VER1/0270-1135":"QC","VER1/0270-1151":"Miller QC Green","VER1/0270-1152":"QC Green","VER1/0270-1153":"Miller QC Green","VER1/0270-1154":"QC Green"};

const CAMERA_ORDER = ['HDMI','QC','QC Green','Miller HDMI','Miller QC','Miller QC Green'];
const CAMERA_COLORS = {'HDMI':'#2563eb','QC':'#059669','QC Green':'#16a34a','Miller HDMI':'#7c3aed','Miller QC':'#d97706','Miller QC Green':'#dc2626'};

function CameraView({ rows, weeks, allWeeks }) {
  const [showAll, setShowAll] = useState(false);
  const displayWeeks = showAll ? allWeeks : weeks;

  // Build camera type → week → total qty
  const cameraData = useMemo(() => {
    const map = {};
    CAMERA_ORDER.forEach(c => { map[c] = { weekTotals: {}, parts: new Set() }; });

    rows.forEach(r => {
      const cam = CAMERA_MAP[r.part_id];
      if (!cam) return;
      if (!map[cam]) map[cam] = { weekTotals: {}, parts: new Set() };
      map[cam].parts.add(r.part_id);
      Object.entries(r.weeks).forEach(([w, qty]) => {
        map[cam].weekTotals[w] = (map[cam].weekTotals[w] || 0) + qty;
      });
    });

    return CAMERA_ORDER.map(cam => ({
      camera: cam,
      weekTotals: map[cam] ? map[cam].weekTotals : {},
      partCount: map[cam] ? map[cam].parts.size : 0,
    })).filter(d => d.partCount > 0);
  }, [rows]);

  // Grand total per week
  const grandTotals = useMemo(() => {
    const gt = {};
    cameraData.forEach(({ weekTotals }) => {
      Object.entries(weekTotals).forEach(([w, v]) => { gt[w] = (gt[w] || 0) + v; });
    });
    return gt;
  }, [cameraData]);

  if (cameraData.length === 0) return <div style={{textAlign:'center',color:'#94a3b8',paddingTop:60}}>No camera-mapped parts in current selection.</div>;

  return (
    <div>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:14,flexWrap:'wrap',gap:8}}>
        <div style={{color:'#64748b',fontSize:13}}>
          Weekly build plan by camera type · <span style={{color:'#0f172a',fontWeight:600}}>{displayWeeks.length}</span> weeks shown
        </div>
        <button onClick={()=>setShowAll(v=>!v)} style={{fontSize:12,color:'#2563eb',background:'transparent',border:'1px solid #cbd5e1',borderRadius:7,padding:'5px 12px',cursor:'pointer'}}>
          {showAll ? 'Show near-term only' : `Show all ${allWeeks.length} weeks`}
        </button>
      </div>

      <div style={{overflowX:'auto',borderRadius:10,border:'1px solid #e2e8f0'}}>
        <table style={{minWidth:'100%',borderCollapse:'collapse',fontSize:13}}>
          <thead>
            <tr style={{background:'#f1f5f9',fontSize:11,textTransform:'uppercase',letterSpacing:'0.05em',color:'#64748b'}}>
              <th style={{position:'sticky',left:0,zIndex:10,background:'#f1f5f9',padding:'10px 16px',textAlign:'left',borderBottom:'1px solid #e2e8f0',borderRight:'1px solid #e2e8f0',minWidth:160,whiteSpace:'nowrap'}}>Camera Type</th>
              {displayWeeks.map(w => <th key={w} style={{padding:'10px 10px',textAlign:'center',borderBottom:'1px solid #e2e8f0',minWidth:76,whiteSpace:'nowrap'}}>{fmtWeek(w)}</th>)}
            </tr>
          </thead>
          <tbody>
            {cameraData.map(({ camera, weekTotals, partCount }) => {
              const color = CAMERA_COLORS[camera] || '#64748b';
              return (
                <tr key={camera} style={{borderBottom:'1px solid #e2e8f0'}}>
                  <td style={{position:'sticky',left:0,zIndex:5,background:'#ffffff',padding:'11px 16px',borderRight:'1px solid #e2e8f0'}}>
                    <div style={{display:'flex',alignItems:'center',gap:8}}>
                      <div style={{width:4,height:20,borderRadius:2,background:color,flexShrink:0}}/>
                      <div>
                        <div style={{color,fontWeight:700,fontSize:13}}>{camera}</div>
                        <div style={{color:'#94a3b8',fontSize:11,marginTop:1}}>{partCount} part{partCount!==1?'s':''}</div>
                      </div>
                    </div>
                  </td>
                  {displayWeeks.map(w => {
                    const qty = weekTotals[w] || 0;
                    return (
                      <td key={w} style={{padding:'11px 10px',textAlign:'center',whiteSpace:'nowrap',background: qty > 0 ? color+'0d' : '#ffffff'}}>
                        {qty > 0
                          ? <span style={{color,fontWeight:700}}>{fmtQty(qty)}</span>
                          : <span style={{color:'#cbd5e1'}}>—</span>}
                      </td>
                    );
                  })}
                </tr>
              );
            })}

            {/* Grand total row */}
            <tr style={{background:'#f8fafc',borderTop:'2px solid #e2e8f0'}}>
              <td style={{position:'sticky',left:0,zIndex:5,background:'#f8fafc',padding:'11px 16px',borderRight:'1px solid #e2e8f0'}}>
                <div style={{color:'#0f172a',fontWeight:700,fontSize:13}}>Total</div>
                <div style={{color:'#94a3b8',fontSize:11,marginTop:1}}>all camera types</div>
              </td>
              {displayWeeks.map(w => {
                const qty = grandTotals[w] || 0;
                return (
                  <td key={w} style={{padding:'11px 10px',textAlign:'center',whiteSpace:'nowrap'}}>
                    {qty > 0
                      ? <span style={{color:'#0f172a',fontWeight:700}}>{fmtQty(qty)}</span>
                      : <span style={{color:'#cbd5e1'}}>—</span>}
                  </td>
                );
              })}
            </tr>
          </tbody>
        </table>
      </div>

      {/* Note about unmapped parts */}
      {rows.some(r => !CAMERA_MAP[r.part_id]) && (
        <div style={{marginTop:12,fontSize:12,color:'#94a3b8'}}>
          ⚠ Some parts in the current view have no camera type assigned and are excluded from this summary.
        </div>
      )}
    </div>
  );
}

ReactDOM.createRoot(document.getElementById('root')).render(<App/>);
</script>
</body>
</html>
