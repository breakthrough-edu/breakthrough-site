// Picker page script for build/event-photos.py pick (copied verbatim as app.js). Data comes from data.js (window.PICKER_DATA = {key, title, want, items}); picks are saved to the artifact db at picks/<key>.
const DATA=window.PICKER_DATA;
const SET=DATA,KEY=DATA.key;
const SHOT={'group-photo':'合照','small-group':'几个人','crowd':'全场','duo':'两人','solo':'单人','detail':'细节','venue':'场地'};
let picked=new Set(),filter='all',db=null,timer=null;
const $=id=>document.getElementById(id);
$('title').textContent=SET.title;$('want').textContent=SET.want;
try{const l=JSON.parse(localStorage.getItem('pick-'+KEY)||'[]');picked=new Set(l)}catch(e){}
const GR=[...new Set(SET.items.map(i=>i.grp).filter(Boolean))];
const F=[['all','全部'],['hero','最好的'],['picked','已选'],['group','合照 · 全场'],['people','两三人'],['solo','单人']].concat(GR.map(g=>['g:'+g,g]));
function show(it){if(filter.startsWith('g:'))return it.grp===filter.slice(2);if(filter==='hero')return it.hero;if(filter==='picked')return picked.has(it.id);if(filter==='group')return ['group-photo','crowd'].includes(it.shot);if(filter==='people')return ['duo','small-group'].includes(it.shot);if(filter==='solo')return it.shot==='solo';return true}
function draw(){
  $('chips').innerHTML='';F.forEach(([k,t])=>{const b=document.createElement('button');b.type='button';b.id='f-'+k.replace(/[^a-z0-9]/gi,'_');b.textContent=t;b.setAttribute('aria-pressed',k===filter);b.onclick=()=>{filter=k;draw()};$('chips').append(b)});
  const g=$('grid');g.innerHTML='';
  SET.items.filter(show).forEach(it=>{const b=document.createElement('button');b.type='button';b.className='ph';b.id='p-'+it.id;b.setAttribute('aria-pressed',picked.has(it.id));b.title=it.note;
    b.innerHTML='<img loading="lazy" width="'+it.w+'" height="'+it.h+'" src="'+it.src+'" alt=""><span class="n">'+it.id.replace(/^DSC[F0]?/,'').replace(/^2026\d{4}_/,'')+'</span><span class="tick">✓</span><span class="m"><span>'+(it.grp?it.grp+' · ':'')+(SHOT[it.shot]||it.shot)+'</span>'+(it.hero?'<i>●</i>':'')+'</span>';
    b.onclick=()=>{picked.has(it.id)?picked.delete(it.id):picked.add(it.id);b.setAttribute('aria-pressed',picked.has(it.id));count();save()};g.append(b)});
  count()}
function count(){$('n').textContent=picked.size}
function save(){try{localStorage.setItem('pick-'+KEY,JSON.stringify([...picked]))}catch(e){}
  if(!db){$('state').textContent='只存在这个浏览器';return}
  $('state').textContent='存档中';clearTimeout(timer);
  timer=setTimeout(()=>db.doc('picks/'+KEY).set({ids:[...picked],count:picked.size,updatedAt:new Date().toISOString()}).then(()=>$('state').textContent='已存 '+picked.size+' 张').catch(()=>$('state').textContent='没存到, 再点一张试试'),700)}
$('size').onclick=function(){const on=$('grid').classList.toggle('big');this.setAttribute('aria-pressed',on);this.textContent=on?'缩小':'放大'};
draw();
(window.claude?claude.use('db'):Promise.resolve(null)).then(async d=>{db=d;if(!d){$('state').textContent='只存在这个浏览器';return}
  try{const s=await d.doc('picks/'+KEY).get();if(s.exists){const ids=(s.data()||{}).ids||[];if(ids.length||!picked.size){picked=new Set(ids);draw()}}$('state').textContent='已存 '+picked.size+' 张'}catch(e){$('state').textContent='只存在这个浏览器'}});
