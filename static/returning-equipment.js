const EQUIPMENT_COMPONENTS = {
  bfSword: { name: '暴风之剑', image: '/static/returning-equipment/component-bf-sword.jpg' },
  recurveBow: { name: '反曲之弓', image: '/static/returning-equipment/component-recurve-bow.jpg' },
  needlesslyLargeRod: { name: '无用大棒', image: '/static/returning-equipment/component-needlessly-large-rod.jpg' },
  tear: { name: '女神之泪', image: '/static/returning-equipment/component-tear-of-the-goddess.jpg' },
  chainVest: { name: '锁子甲', image: '/static/returning-equipment/component-chain-vest.jpg' },
  negatronCloak: { name: '负极斗篷', image: '/static/returning-equipment/component-negatron-cloak.jpg' },
  giantsBelt: { name: '巨人腰带', image: '/static/returning-equipment/component-giants-belt.jpg' },
  sparringGloves: { name: '拳套', image: '/static/returning-equipment/component-sparring-gloves.jpg' },
};

const RETURNING_EQUIPMENT = [
  {
    name: '鬼索的狂暴之刃',
    image: '/static/returning-equipment/guinsoos-rageblade.png',
    basicDesc: '+10%攻击速度 +10法术加成',
    desc: '每次攻击提供5%额外攻击速度。这个效果可叠加！  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.recurveBow, EQUIPMENT_COMPONENTS.needlesslyLargeRod],
  },
  {
    name: '卢安娜的飓风',
    image: '/static/returning-equipment/runaans-hurricane.png',
    basicDesc: '+20%攻击速度 +20魔法抗性',
    desc: '携带者的攻击会对附近的另一名敌人发射一个弹体，造成携带者50%攻击力【攻击力】的物理伤害。  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.recurveBow, EQUIPMENT_COMPONENTS.negatronCloak],
  },
  {
    name: '灵风',
    image: '/static/returning-equipment/zephyr.png',
    basicDesc: '+150生命上限 +20魔法抗性',
    desc: '战斗开始时：在棋盘对面召唤一道飓风，来将与飓风相距最近的那个敌人移出战斗5秒。  [无视控制免疫效果。] [怪兽入侵专属] [唯一-每位英雄仅限1件]',
    components: [EQUIPMENT_COMPONENTS.negatronCloak, EQUIPMENT_COMPONENTS.giantsBelt],
  },
  {
    name: '基克的先驱',
    image: '/static/returning-equipment/zekes-herald.png',
    basicDesc: '+150生命上限 +20物理加成',
    desc: '战斗开始时：提供【攻击速度】20%攻击速度给携带者和同一排1格内的友军们。  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.bfSword, EQUIPMENT_COMPONENTS.giantsBelt],
  },
  {
    name: '静止法衣',
    image: '/static/returning-equipment/shroud-of-stillness.png',
    basicDesc: '+20护甲 +20%暴击率',
    desc: '战斗开始时：射出一道光束，对敌人们施加35%破法。  [怪兽入侵专属] 破法：最大法力值提升，持续到施放技能为止。 [唯一-每位英雄仅限1件]',
    components: [EQUIPMENT_COMPONENTS.chainVest, EQUIPMENT_COMPONENTS.sparringGloves],
  },
  {
    name: '兹若特传送门',
    image: '/static/returning-equipment/zzrot-portal.png',
    basicDesc: '+150生命上限 +20%攻击速度',
    desc: '召唤一个大型虚空生物。它的强度会在每个阶段提升。  [怪兽入侵专属] [唯一-每位英雄仅限1件]',
    components: [EQUIPMENT_COMPONENTS.recurveBow, EQUIPMENT_COMPONENTS.giantsBelt],
  },
  {
    name: '疾射火炮',
    image: '/static/returning-equipment/rapid-firecannon.png',
    basicDesc: '+50%攻击速度',
    desc: '攻击距离+1。',
    components: [EQUIPMENT_COMPONENTS.recurveBow, EQUIPMENT_COMPONENTS.recurveBow],
  },
  {
    name: '钢铁烈阳之匣',
    image: '/static/returning-equipment/locket-of-the-iron-solari.png',
    basicDesc: '+20护甲 +20法术加成',
    desc: '战斗开始时：携带者和同一排2格内的友军们获得持续15秒的300/350/400护盾值（随携带者星级增加）。  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.needlesslyLargeRod, EQUIPMENT_COMPONENTS.chainVest],
  },
  {
    name: '能量圣杯',
    image: '/static/returning-equipment/chalice-of-power.png',
    basicDesc: '+20魔法抗性 +10法力值',
    desc: '战斗开始时：提供25%法术加成给携带者和同一排1格内的友军们。  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.tear, EQUIPMENT_COMPONENTS.negatronCloak],
  },
  {
    name: '狂徒铠甲',
    image: '/static/returning-equipment/warmogs-armor.png',
    basicDesc: '+500生命上限',
    desc: '每秒回复 5% 最大生命。  [怪兽入侵专属]',
    components: [EQUIPMENT_COMPONENTS.giantsBelt, EQUIPMENT_COMPONENTS.giantsBelt],
  },
  {
    name: '斯塔缇克电刃',
    image: '/static/returning-equipment/statikk-shiv.png',
    basicDesc: '+20%攻击速度 +10法力值',
    desc: '每第3次攻击对4名敌人造成30魔法伤害和持续5秒的30%魔抗击碎。  [怪兽入侵专属] 魔抗击碎：降低魔抗值',
    components: [EQUIPMENT_COMPONENTS.recurveBow, EQUIPMENT_COMPONENTS.tear],
  },
  {
    name: '蓝霸符',
    image: '/static/returning-equipment/blue-buff.png',
    basicDesc: '+10法力值 +10物理加成 +10法术加成',
    desc: '施放技能的法力值消耗降低10。如果携带者在施放技能后的3秒内至少参与了一次击败，就会获得10法力值。  [怪兽入侵专属] [唯一-每位英雄仅限1件]',
    components: [EQUIPMENT_COMPONENTS.tear, EQUIPMENT_COMPONENTS.tear],
  },
];

const grid = document.querySelector('#returningEquipmentGrid');
const themeToggle = document.querySelector('#themeToggle');
const themeIcon = document.querySelector('#themeIcon');
const themeText = document.querySelector('#themeText');

setReturningEquipmentTheme(localStorage.getItem('theme') || 'light');
themeToggle?.addEventListener('click', () => {
  setReturningEquipmentTheme(document.documentElement.dataset.theme === 'dark' ? 'light' : 'dark');
});

function setReturningEquipmentTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem('theme', theme);
  window.jccApplyThemeToggleState?.(theme, themeToggle, themeIcon, themeText);
}

function renderReturningEquipment() {
  if (grid.children.length > 0) return;
  grid.replaceChildren(...RETURNING_EQUIPMENT.map(createEquipmentCard));
}

function createEquipmentCard(item) {
  const card = document.createElement('article');
  card.className = 'returning-equipment-card';

  const imageWrap = document.createElement('div');
  imageWrap.className = 'returning-equipment-image-wrap';

  const image = document.createElement('img');
  image.className = 'returning-equipment-image';
  image.src = item.image;
  image.alt = item.name;
  image.loading = 'lazy';
  image.decoding = 'async';
  imageWrap.append(image);

  const body = document.createElement('div');
  body.className = 'returning-equipment-body';

  const label = document.createElement('p');
  label.className = 'returning-equipment-label';
  label.textContent = '回归装备';

  const title = document.createElement('h2');
  title.textContent = item.name;

  const stats = document.createElement('p');
  stats.className = 'returning-equipment-stats';
  stats.textContent = item.basicDesc;

  const desc = document.createElement('p');
  desc.className = 'returning-equipment-desc';
  desc.textContent = item.desc;

  const synthesis = createSynthesis(item.components);

  body.append(label, title, stats, desc, synthesis);
  card.append(imageWrap, body);
  return card;
}

function createSynthesis(components) {
  const wrap = document.createElement('div');
  wrap.className = 'returning-equipment-synthesis';

  const label = document.createElement('span');
  label.className = 'returning-equipment-synthesis-label';
  label.textContent = '合成';
  wrap.append(label);

  const list = document.createElement('div');
  list.className = 'returning-equipment-components';
  components.forEach((component, index) => {
    if (index > 0) {
      const plus = document.createElement('span');
      plus.className = 'returning-equipment-component-plus';
      plus.textContent = '+';
      list.append(plus);
    }
    list.append(createComponent(component));
  });
  wrap.append(list);
  return wrap;
}

function createComponent(component) {
  const item = document.createElement('span');
  item.className = 'returning-equipment-component';

  const image = document.createElement('img');
  image.className = 'returning-equipment-component-image';
  image.src = component.image;
  image.alt = component.name;
  image.loading = 'lazy';
  image.decoding = 'async';

  const name = document.createElement('span');
  name.textContent = component.name;

  item.append(image, name);
  return item;
}

renderReturningEquipment();
