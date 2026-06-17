const SPECIAL_MECHANICS = [
  {
    name: '迅捷蟹（经济）',
    skill: '成长战利品',
    filter: 'economy',
    skillDesc: '受到攻击后会逃跑的胆小单位，每生存1秒获得1成长层数，如果战斗结束时仍然存活，则会额外获得10成长层数。（当前成长层数：0） 倒下时会掉落金币，每有100层成长层数，额外掉落1金币。',
    image: '/static/special-mechanics/avatars/8357.png',
  },
  {
    name: '迅捷蟹（战力）',
    skill: '跳舞',
    filter: 'power',
    skillDesc: '毫无危险性的坦克迅捷蟹，通过跳舞来吸引周围敌人的仇恨，会在4-1完成一次华丽的进化！',
    image: '/static/special-mechanics/avatars/8358.png',
  },
  {
    name: '胖胖龙（经济）',
    skill: '危险大奖',
    filter: 'economy',
    skillDesc: '当小小英雄生命值降至30后，获得25金币和一个金铲铲/金锅锅。',
    image: '/static/special-mechanics/avatars/8361.png',
  },
  {
    name: '胖胖龙（战力）',
    skill: '危险大奖',
    filter: 'power',
    skillDesc: '当玩家受到第一次致死伤害时，胖胖龙将小小英雄血量锁定至1，并为所有友军提供30%双强和30%全能汲取。',
    image: '/static/special-mechanics/avatars/8362.png',
  },
  {
    name: '装备商人（经济）',
    skill: '提供装备',
    filter: 'economy',
    skillDesc: '装备商人会打开一个特殊的打造商店，商店由随机的散件、成装、神器、光明装组成。根据选择的装备价值，等待若干玩家对战回合后获得。',
    image: '/static/special-mechanics/avatars/8363.png',
  },
  {
    name: '装备商人（战力）',
    skill: '提供装备',
    filter: 'power',
    skillDesc: '战斗开始时，商人朝若干个最强且身上装备未满3件的友军扔出1件临时推荐装备，扔出的装备数量随着阶段数增长。',
    image: '/static/special-mechanics/avatars/8364.png',
  },
  {
    name: '魄罗粉丝（经济）',
    skill: '喝彩',
    filter: 'economy',
    skillDesc: '赢得战斗会获得一个可爱的魄罗粉丝，观众席满员后，狂热的魄罗在友军击败敌人时50%扔出金币或高价值弈子。',
    image: '/static/special-mechanics/avatars/8366.png',
  },
  {
    name: '魄罗粉丝（战力）',
    skill: '喝彩',
    filter: 'power',
    skillDesc: '赢得战斗会获得一个可爱的魄罗粉丝，观众席满员后，狂热的魄罗们会在棋盘上点亮2个聚光灯格，为棋子提供20%伤害增幅以及3法力恢复。',
    image: '/static/special-mechanics/avatars/8395.png',
  },
  {
    name: '卡牌大师（经济）',
    skill: '逆转裁判（投放）',
    filter: 'economy',
    skillDesc: '逆转裁判奖励坚持到回合结束的我方剩余弈子，根据弈子个数获得玩家经验值。',
    image: '/static/special-mechanics/avatars/8380.png',
  },
  {
    name: '卡牌大师（战力）',
    skill: '逆转裁判（战力）',
    filter: 'power',
    skillDesc: '逆转裁判开场对敌方最强弈子发出红牌警告，使其造成的伤害降低30%，持续6秒；并对我方存活的最后一名弈子发出蓝牌，使其获得巨额提升！',
    image: '/static/special-mechanics/avatars/8381.png',
  },
  {
    name: '爆裂球果（经济）',
    skill: '爆炸球果（投放）',
    filter: 'economy',
    skillDesc: '现在和每4个回合后，装备区会长出爆裂球果，拖拽它至任意我方备战席弈子上，该弈子会被卖出，同时商店会免费刷新一次，且刷出的弈子与原弈子必定同费且不同名。',
    image: '/static/special-mechanics/avatars/8382.png',
  },
  {
    name: '阿木木（经济）',
    skill: '阿木木（投放）',
    filter: 'economy',
    skillDesc: '将不需要的装备和弈子置入其中，会出现意想不到的惊喜!',
    image: '/static/special-mechanics/avatars/8384.png',
  },
  {
    name: '阿木木（战力）',
    skill: '阿木木（战力）',
    filter: 'power',
    skillDesc: '阿木木会在受到伤害时哭泣，他的泪水对敌人造成每秒100(【法术加成】)魔法伤害，商店中随机刷新出给她的情书，每购买一次，可使阿木木的法术加成提高5%。',
    image: '/static/special-mechanics/avatars/8385.png',
  },
  {
    name: '防御塔（经济）',
    skill: '防御塔（投放）',
    filter: 'economy',
    skillDesc: '击败敌人会累积防御塔的建造进度，防御塔建成后，提高我方4/5费弈子的刷新概率。',
    image: '/static/special-mechanics/avatars/8388.png',
  },
  {
    name: '防御塔（战力）',
    skill: '防御塔（战力）',
    filter: 'power',
    skillDesc: '防御塔是一名远程物理重炮手，射程无限、免疫控制、无法移动，放前两排时，它每次被摧毁会获得最大生命值；放后两排时，它击败敌方单位会获得永久攻击力。',
    image: '/static/special-mechanics/avatars/8378.png',
  },
  {
    name: '奶酪首领（战力）',
    skill: '芝士老鼠（战力）',
    filter: 'power',
    skillDesc: '奶酪首领会向我方最强弈子投掷奶酪，获得奶酪的友军化身鼠王变异体，获得控制免疫和伤害减免效果。',
    image: '/static/special-mechanics/avatars/8387.png',
  },
  {
    name: '卑鄙茧房',
    skill: '蛛网陷阱',
    filter: 'power',
    skillDesc: '这是一个危险的陷阱！',
    image: '/static/special-mechanics/avatars/8391.png',
  },
];

const list = document.querySelector('#specialMechanicList');
const filterButtons = Array.from(document.querySelectorAll('.mechanic-filter-button'));
const themeToggle = document.querySelector('#themeToggle');
const themeIcon = document.querySelector('#themeIcon');
const themeText = document.querySelector('#themeText');
let activeFilter = 'all';

setSpecialMechanicsTheme(localStorage.getItem('theme') || 'light');
themeToggle?.addEventListener('click', () => {
  setSpecialMechanicsTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

filterButtons.forEach((button) => {
  button.addEventListener('click', () => {
    activeFilter = button.dataset.filter || 'all';
    filterButtons.forEach((item) => {
      const isActive = item === button;
      item.classList.toggle('active', isActive);
      item.setAttribute('aria-selected', String(isActive));
    });
    renderMechanics();
  });
});

function setSpecialMechanicsTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, themeToggle, themeIcon, themeText);
}

function renderMechanics() {
  const items = SPECIAL_MECHANICS.filter((item) => activeFilter === 'all' || item.filter === activeFilter);
  list.replaceChildren(...items.map(createMechanicCard));
}

function createMechanicCard(item) {
  const card = document.createElement('article');
  card.className = `special-mechanic-card ${item.filter}`;

  const imageWrap = document.createElement('div');
  imageWrap.className = 'special-mechanic-image-wrap';

  const image = document.createElement('img');
  image.className = 'special-mechanic-image';
  image.src = item.image;
  image.alt = item.name;
  image.loading = 'lazy';
  image.decoding = 'async';
  imageWrap.append(image);

  const body = document.createElement('div');
  body.className = 'special-mechanic-body';

  const meta = document.createElement('div');
  meta.className = 'special-mechanic-meta';
  meta.textContent = item.filter === 'power' ? '战力形态' : '经济形态';

  const title = document.createElement('h2');
  title.textContent = item.name;

  const skill = document.createElement('p');
  skill.className = 'special-mechanic-skill';
  skill.textContent = item.skill;

  const summary = document.createElement('p');
  summary.className = 'special-mechanic-summary';
  summary.textContent = item.skillDesc;

  body.append(meta, title, skill, summary);
  card.append(imageWrap, body);
  return card;
}

renderMechanics();
