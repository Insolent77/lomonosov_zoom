"""Self-contained UI demo. No student data and no real Zoom or chat integration."""
PAGE=r'''<!doctype html><html lang="ru"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Мой Ломоносов — демонстрация занятий</title>
<style>
:root{font:15px system-ui,Segoe UI,sans-serif;color:#14213c;background:#f5f7fc}*{box-sizing:border-box}body{margin:0}.top{background:white;border-bottom:1px solid #e3e9f3;padding:15px max(22px,calc((100vw - 1080px)/2));display:flex;align-items:center;justify-content:space-between;gap:12px}.brand{font-weight:800;font-size:18px}.wrap{max-width:1100px;margin:30px auto;padding:0 18px}.muted{color:#71829e}.note{background:#fff7e7;border:1px solid #f4da9b;border-radius:13px;padding:14px 18px;margin:19px 0}nav{display:flex;gap:8px;flex-wrap:wrap}nav a,.pill{padding:9px 15px;border-radius:9px;text-decoration:none;background:#edf2fa;color:#50607c;font-weight:700}nav a.active{background:#376ce5;color:white}.cards{display:grid;grid-template-columns:1fr 1fr;gap:18px}.card{background:white;border:1px solid #e1e7f1;border-radius:16px;padding:23px;margin-bottom:16px;box-shadow:0 4px 14px #14264008}h1{font-size:27px;margin:0 0 7px}h2{font-size:19px;margin:0 0 16px}h3{font-size:16px;margin:0 0 7px}.status{display:inline-block;border-radius:6px;background:#ebf2fe;color:#295abd;font-size:12px;padding:5px 8px}.details{display:flex;gap:13px;flex-wrap:wrap;margin:15px 0;color:#62738d;font-size:13px}button{cursor:pointer;border:0;border-radius:9px;padding:11px 16px;background:#376be7;color:white;font-weight:700}button:disabled{cursor:not-allowed;background:#e7ecf6;color:#97a6bf}.outline{background:#eaf0fe;color:#2855bf}.chat{background:#f6f8fd;border-radius:12px;padding:15px;min-height:180px}.msg{background:white;border:1px solid #e6eaf4;border-radius:12px;padding:14px;margin:10px 0;max-width:490px}.msg p{margin:9px 0}.msg a{color:#2c64d9}.mini{font-size:12px;color:#7888a2}.hint{background:#eef4fd;border-radius:9px;padding:13px;font-size:13px;color:#4e648c}.inline{display:flex;gap:8px;flex-wrap:wrap;align-items:center}.inline button{margin:4px 0}.hidden{display:none!important}input{padding:10px;border:1px solid #cbd5e5;border-radius:9px}footer{font-size:13px;color:#8792a5;padding-bottom:40px}@media(max-width:750px){.cards{grid-template-columns:1fr}.top{padding:15px}.wrap{margin:20px auto}}
</style></head><body><header class="top"><div class="brand">🟠 Мой Ломоносов · тестовый сайт</div><nav><a id="nav-teacher" href="/teacher">Преподаватель</a><a id="nav-chats" href="/chats">Учебные чаты</a><a href="/recordings">Полученные записи</a></nav></header>
<main class="wrap"><h1 id="page-title">Кабинет преподавателя</h1><p class="muted" id="page-desc">Занятия и вход в Zoom по расписанию.</p>
<div class="note">Это <b>интерактивная демонстрация</b> с вымышленными уроками. Кнопка не подключена к настоящему Zoom. Реальные записи, Django и настоящие учебные чаты здесь пока не связаны.</div>
<div class="card"><div class="inline"><b>Тестирование временного ограничения:</b><button id="test-time" class="outline">Установить 15 минут до урока</button><button id="reset-time" class="outline">Текущее время</button><span id="clock" class="mini"></span></div>
<p class="mini">Правило: вход доступен за 15 минут до начала и до конца урока. Кнопки симуляции записи работают только в этом браузере.</p></div>
<div id="teacher" class="cards"></div><div id="chats" class="cards hidden"></div>
<footer>После завершения занятия Zoom присылает recording.completed. В реальной версии сервер проверяет подпись и сопоставляет запись с уроком, Zoom-аккаунтом и чатом.</footer>
</main><script>
const ZONE='Europe/Moscow';
const mocks=[
{id:101,group:'[8] -1.87 Вероника Хваткова',topic:'Математика',teacher:'Преподаватель 1',room:'Zoom 5',chat:'chat-101', offset:15,minutes:90},
{id:102,group:'7 класс · Группа А',topic:'Физика',teacher:'Преподаватель 2',room:'Zoom 2',chat:'chat-102',offset:75,minutes:60}
];
const prefix='lomo-test-flow-v2:';
let simulated=false, base=Date.now();
const state=()=>JSON.parse(sessionStorage.getItem(prefix+'state')||'{}');
const save=(x)=>sessionStorage.setItem(prefix+'state',JSON.stringify(x));
function esc(v){return String(v).replace(/[&<>"']/g,s=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[s]))}
function cur(){return simulated?base:Date.now()}
function fmt(t){return new Intl.DateTimeFormat('ru-RU',{timeZone:ZONE,hour:'2-digit',minute:'2-digit'}).format(t)}
const start=(l)=>base+l.offset*60000;
const end=(l)=>start(l)+l.minutes*60000;
function render(){
const onChat=location.pathname==='/chats';
document.querySelector('#nav-'+(onChat?'chats':'teacher')).classList.add('active');
document.getElementById('page-title').textContent=onChat?'Учебные чаты':'Кабинет преподавателя';
document.getElementById('page-desc').textContent=onChat?'Условная переписка и уведомление о готовой записи':'Кнопка входа появляется за 15 минут до занятия';
document.getElementById('teacher').classList.toggle('hidden',onChat);
document.getElementById('chats').classList.toggle('hidden',!onChat);
document.getElementById('clock').textContent='Тестовое время: '+fmt(cur())+' (МСК)';
const st=state();
document.getElementById('teacher').innerHTML=mocks.map(l=>{
const ready=cur()>=start(l)-15*60000&&cur()<end(l), started=!!st[l.id]?.started,recorded=!!st[l.id]?.recorded;
const status=recorded?'Запись готова':started?'Занятие начато':ready?'Можно начать':'Ожидает начала';
return '<section class="card"><span class="status">'+status+'</span><h2 style="margin-top:13px">'+esc(l.group)+'</h2><b>'+esc(l.topic)+'</b><div class="details"><span>🕒 '+fmt(start(l))+'–'+fmt(end(l))+' МСК</span><span>📍 '+esc(l.room)+'</span><span>👥 '+esc(l.chat)+'</span></div><button '+(!ready||started?'disabled':'')+' data-start="'+l.id+'">'+(started?'Вход выполнен':'Начать занятие')+'</button><p class="mini">'+(ready?'В продакшене кнопка откроет адрес Zoom 5/2 из модели локации.':'Кнопка пока недоступна: до начала больше 15 минут либо занятие завершено.')+'</p><div class="hint">Для демонстрации: после входа можно имитировать готовность облачной записи.</div><div style="margin-top:12px"><button class="outline" data-complete="'+l.id+'" '+(!started||recorded?'disabled':'')+'>Сымитировать готовую запись</button></div></section>'
}).join('');
document.getElementById('chats').innerHTML=mocks.map(l=>{
const entry=st[l.id];return '<section class="card"><h2>'+esc(l.group)+'</h2><div class="details"><span>'+esc(l.chat)+'</span><span>'+esc(l.room)+'</span></div><div class="chat"><div class="msg"><b>Мой Ломоносов · системное сообщение</b><p>Занятие: '+esc(l.topic)+'</p><span class="mini">'+fmt(start(l))+'–'+fmt(end(l))+' (МСК)</span></div>'+(entry?.recorded?'<div class="msg"><b>🎬 Мой Ломоносов · бот</b><p>Запись занятия готова!</p><a href="#" onclick="alert(\'Демонстрация: в настоящей версии здесь будет ссылка Zoom с кодом просмотра.\');return false">Открыть запись занятия ↗</a><p class="mini">Отправлено автоматически в '+esc(l.chat)+'</p></div>':'<div class="msg muted">Ссылка появится здесь после симуляции готовой записи.</div>')+'</div></section>'
}).join('');
document.querySelectorAll('[data-start]').forEach(b=>b.onclick=()=>{let st=state();st[b.dataset.start]={started:true,recorded:false};save(st);render();alert('Демо: преподаватель перешёл бы в назначенный Zoom. Запись включается настройками Zoom.');});
document.querySelectorAll('[data-complete]').forEach(b=>b.onclick=()=>{let st=state();st[b.dataset.complete]={started:true,recorded:true};save(st);render();alert('Демо: recording.completed обработан; ссылка доставлена в тестовый чат.');});
}
document.getElementById('test-time').onclick=()=>{simulated=true;base=Date.now();render()};
document.getElementById('reset-time').onclick=()=>{simulated=false;render()};
render();setInterval(()=>{if(!simulated)render()},60000);
</script></body></html>'''
