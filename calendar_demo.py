"""Google Calendar-like scheduling demo, entirely fictional data."""
PAGE = r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Календарь занятий — Мой Ломоносов</title>
<style>
*{box-sizing:border-box}body{font:14px system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;background:#fff;color:#1f2937}
header{height:70px;display:flex;align-items:center;gap:17px;padding:0 23px;border-bottom:1px solid #e5e7eb;flex-wrap:wrap}
.logo{font-weight:800;font-size:19px;white-space:nowrap}.main{display:flex;height:calc(100vh - 70px);min-height:620px}
aside{width:215px;flex-shrink:0;border-right:1px solid #e8edf2;padding:22px 14px;overflow:auto}
label{display:flex;align-items:center;gap:9px;padding:9px 5px;cursor:pointer;font-size:13px}
input[type=checkbox]{accent-color:#4a6be7}.muted{color:#79879b}.hint{font-size:12px;line-height:1.6;background:#fff5dc;border-radius:11px;padding:12px;margin-top:20px}
button,select,input[type=date]{background:white;border:1px solid #dce2e9;border-radius:9px;padding:9px 12px;color:#334155;font:inherit;cursor:pointer}
button:hover{background:#f5f7fa}.buttons{display:flex;gap:6px;align-items:center}.active{background:#e8efff!important;color:#2d58d5!important;font-weight:700}
h1{font-size:21px;white-space:nowrap;margin:0 7px}.workspace{flex:1;min-width:0;display:flex;flex-direction:column;overflow:hidden}
.toolbar{padding:16px;display:flex;align-items:center;gap:12px;flex-wrap:wrap;border-bottom:1px solid #edf0f4}
.board{flex:1;overflow:auto;background:white}.week-head{display:grid;position:sticky;top:0;z-index:5;background:white;border-bottom:1px solid #e5e7eb}
.day-head{min-width:0;text-align:center;padding:12px 4px;border-left:1px solid #f0f2f7;font-weight:650}
.day-head small{display:block;font-weight:500;color:#8994a6}.grid-area{position:relative;display:grid}
.hours{position:absolute;left:0;width:56px;top:0;bottom:0;pointer-events:none}
.hour{position:absolute;right:8px;transform:translateY(-9px);font-size:11px;color:#8794a8}
.column{position:relative;border-left:1px solid #e8ecf3;min-width:125px;background:repeating-linear-gradient(to bottom,transparent 0,transparent 59px,#edf0f4 59px,#edf0f4 60px)}
.event{position:absolute;left:3px;right:3px;border-left:4px solid #5a77e9;border-radius:6px;background:#e7edff;color:#264799;padding:5px 6px;font-size:11px;overflow:hidden;text-align:left;cursor:pointer;box-shadow:0 1px 2px #15203b20}
.event b{display:block;line-height:1.25;margin:2px 0}.event span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.event[data-room="Zoom 5"]{background:#e5f4ef;border-color:#1d9a75;color:#147355}
.event[data-room="Zoom 2"]{background:#fff0db;border-color:#e39a29;color:#92601b}
.event[data-room="Zoom 8"]{background:#f2e8ff;border-color:#a365d5;color:#7541a9}
.event:hover{filter:brightness(.95)}
dialog{border:0;border-radius:17px;padding:25px;width:min(460px,95vw);box-shadow:0 17px 55px #0003}dialog::backdrop{background:#18263c70}
dialog h2{margin:0 0 13px}.meta{margin:12px 0;color:#637089}.modal-actions{display:flex;gap:10px;margin-top:20px}.primary{background:#3869e1;color:white}.primary:hover{background:#2e5ccc}
@media(max-width:850px){aside{display:none}header{height:auto;padding:12px}.main{height:calc(100vh - 102px)}.toolbar{padding:10px}}
</style></head><body><header><div class="logo">🟠 Мой Ломоносов</div><div class="muted">/</div><strong>Календарь занятий</strong><a href="/teacher" style="margin-left:auto;color:#5974c5;text-decoration:none">Кабинет преподавателя ↗</a></header>
<div class="main"><aside><b>Локации Zoom</b><p class="muted" style="font-size:12px">Фильтр по кабинетам</p><div id="rooms"></div>
<div class="hint"><b>Тестовые данные</b><p>Расписание пока не связано с Django. Кликни на занятие, чтобы увидеть карточку и кнопку входа в Zoom.</p></div></aside>
<div class="workspace"><div class="toolbar"><button id="today">Сегодня</button><div class="buttons"><button id="prev" aria-label="Назад">‹</button><button id="next" aria-label="Вперёд">›</button></div><h1 id="heading"></h1>
<div class="buttons" style="margin-left:auto"><button data-view="day">День</button><button data-view="week" class="active">Неделя</button></div><input type="date" id="date"></div>
<div id="board" class="board"></div></div></div>
<dialog id="details"><h2 id="dtitle"></h2><div class="meta" id="dmeta"></div><p id="dnote"></p><div class="modal-actions"><button id="dclose">Закрыть</button><button class="primary" id="dstart">Начать занятие</button></div></dialog>
<script>
const zone='Europe/Moscow', rooms=Array.from({length:12},(_,i)=>'Zoom '+(i+1)), selected=new Set(rooms);
let focus=new Date(),view='week';
function iso(d){return d.getFullYear()+'-'+String(d.getMonth()+1).padStart(2,'0')+'-'+String(d.getDate()).padStart(2,'0')}
function plus(d,n){let x=new Date(d);x.setDate(x.getDate()+n);return x}
function weekStart(d){let x=new Date(d);x.setDate(x.getDate()-(x.getDay()+6)%7);return x}
function fmt(d,opt){return new Intl.DateTimeFormat('ru-RU',opt).format(d)}
function displayClock(t){return String(Math.floor(t/60)).padStart(2,'0')+':'+String(t%60).padStart(2,'0')}
const lessons=[
{day:0,start:660,duration:90,group:'[8] -1.87 Вероника Хваткова',room:'Zoom 5',teacher:'Преподаватель 1',chat:'Группа 8'},
{day:0,start:840,duration:60,group:'Математика · 7 класс',room:'Zoom 2',teacher:'Преподаватель 2',chat:'Группа 7'},
{day:1,start:600,duration:90,group:'Русский язык · 9 класс',room:'Zoom 8',teacher:'Преподаватель 3',chat:'Группа 9'},
{day:1,start:780,duration:90,group:'Физика · 8 класс',room:'Zoom 5',teacher:'Преподаватель 1',chat:'Группа 8'},
{day:2,start:720,duration:60,group:'Олимпиадная математика',room:'Zoom 2',teacher:'Преподаватель 2',chat:'Группа 6'},
{day:3,start:960,duration:90,group:'Подготовка к ОГЭ',room:'Zoom 5',teacher:'Преподаватель 1',chat:'Группа 9'},
{day:4,start:690,duration:90,group:'Информатика · 10 класс',room:'Zoom 8',teacher:'Преподаватель 3',chat:'Группа 10'},
{day:5,start:660,duration:90,group:'Математика · 7 класс',room:'Zoom 2',teacher:'Преподаватель 2',chat:'Группа 7'}
];
const roomsList=document.getElementById('rooms');roomsList.innerHTML=rooms.map(x=>'<label><input type="checkbox" checked data-room="'+x+'">'+x+'</label>').join('');
roomsList.querySelectorAll('input').forEach(i=>i.onchange=()=>{if(i.checked)selected.add(i.dataset.room);else selected.delete(i.dataset.room);render()});
function render(){
const first=view==='week'?weekStart(focus):focus, days=view==='week'?7:1;
document.getElementById('heading').textContent=view==='week'?fmt(first,{day:'numeric',month:'short'})+' – '+fmt(plus(first,6),{day:'numeric',month:'long',year:'numeric'}):fmt(first,{day:'numeric',month:'long',year:'numeric'});
document.getElementById('date').value=iso(focus);
document.querySelectorAll('[data-view]').forEach(b=>b.classList.toggle('active',b.dataset.view===view));
const monday=weekStart(focus), shown=Array.from({length:days},(_,i)=>plus(first,i));
const head='<div class="week-head" style="grid-template-columns:56px repeat('+days+',minmax(125px,1fr))"><div></div>'+shown.map(d=>'<div class="day-head"><small>'+fmt(d,{weekday:'short'})+'</small>'+fmt(d,{day:'numeric',month:'short'})+'</div>').join('')+'</div>';
const columns=shown.map(d=>{
const dow=(d.getDay()+6)%7;
const events=lessons.filter(x=>x.day===dow&&selected.has(x.room)).map(l=>{
const top=(l.start-480),height=l.duration;const index=lessons.indexOf(l);
return '<button class="event" data-lesson="'+index+'" data-room="'+l.room+'" style="top:'+top+'px;height:'+height+'px"><span>'+displayClock(l.start)+' – '+displayClock(l.start+l.duration)+'</span><b>'+l.group+'</b><span>'+l.room+'</span></button>'
}).join('');
return '<div class="column">'+events+'</div>'
}).join('');
const hours=Array.from({length:15},(_,i)=>'<span class="hour" style="top:'+(i*60)+'px">'+String(i+8).padStart(2,'0')+':00</span>').join('');
document.getElementById('board').innerHTML=head+'<div class="grid-area" style="height:900px;grid-template-columns:56px repeat('+days+',minmax(125px,1fr))"><div class="hours">'+hours+'</div><div></div>'+columns+'</div>';
document.querySelectorAll('[data-lesson]').forEach(b=>b.onclick=()=>showLesson(lessons[+b.dataset.lesson],shown[Array.from(b.parentElement.parentElement.children).indexOf(b.parentElement)-1]));
}
function showLesson(l,d){const end=l.start+l.duration;document.getElementById('dtitle').textContent=l.group;document.getElementById('dmeta').textContent=fmt(d,{day:'numeric',month:'long'})+' · '+displayClock(l.start)+'–'+displayClock(end)+' · '+l.room;
document.getElementById('dnote').textContent='Преподаватель: '+l.teacher+' · Учебный чат: '+l.chat+'. Ссылка на реальный Zoom пока не подключена.';
const now=new Date(),today=iso(now),nowMin=now.getHours()*60+now.getMinutes();const allowed=iso(d)===today&&nowMin>=l.start-15&&nowMin<end;
const button=document.getElementById('dstart');button.disabled=!allowed;button.title='Демо: подключение Zoom ещё не настроено';button.onclick=()=>alert('Это демонстрационный календарь. Реальный Zoom пока не подключён.');
document.getElementById('details').showModal();}
document.getElementById('dclose').onclick=()=>document.getElementById('details').close();
document.getElementById('prev').onclick=()=>{focus=plus(focus,view==='week'?-7:-1);render()};
document.getElementById('next').onclick=()=>{focus=plus(focus,view==='week'?7:1);render()};
document.getElementById('today').onclick=()=>{focus=new Date();render()};
document.getElementById('date').onchange=e=>{const p=e.target.value.split('-');if(p.length===3){focus=new Date(+p[0],+p[1]-1,+p[2]);render()}};
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{view=b.dataset.view;render()});render();
</script></body></html>'''
