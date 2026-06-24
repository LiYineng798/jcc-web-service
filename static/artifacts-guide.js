const ARTIFACT_GUIDE_CARDS = [
  {
    hero: '厄加特',
    heroImage: '/static/artifacts-guide/heroes/5127_厄加特_s8_urgot.png',
    artifact: '秘银',
    artifactImage: '/static/artifacts-guide/artifacts/6072_密银黎明_silvermere_dawn.jpg',
    evaluation: '普攻持续给对面挂上0.8秒控制，一开大招全员集体被推晕，堪称无限连环眩晕折磨流',
  },
  {
    hero: '努努',
    heroImage: '/static/artifacts-guide/heroes/5121_努努和威朗普_s8_nunu.png',
    artifact: '探索者护臂',
    artifactImage: '/static/artifacts-guide/artifacts/6084_探索者的护臂_seeker_s_armguard.jpg',
    evaluation: '搭配专属强化【当面推球】大幅提升球体游走效率，沿途敌人全被眩晕持续掉血，击杀后靠护臂无限叠双抗法强',
  },
  {
    hero: '维克兹',
    heroImage: '/static/artifacts-guide/heroes/3163_维克兹_s8_velkoz.png',
    artifact: '巫妖之涡',
    artifactImage: '/static/artifacts-guide/artifacts/6086_巫妖之祸_lich_bane.jpg',
    evaluation: '搭配专属强化【霜燃】，搭配巫妖之涡叠层，一个技能直接清屏，解压效果拉满',
  },
  {
    hero: '厄加特',
    heroImage: '/static/artifacts-guide/heroes/5127_厄加特_s8_urgot.png',
    artifact: '巨型九头蛇',
    artifactImage: '/static/artifacts-guide/artifacts/6090_巨型九头蛇_titanichydra.jpg',
    evaluation: '厄加特被动每秒五次攻击，巨型九头蛇能把坦度转化为群体百分比伤害，兼顾控制和打击肉坦的效果',
  },
  {
    hero: '内瑟斯（狗头）',
    heroImage: '/static/artifacts-guide/heroes/1152_内瑟斯_s8_nasus.png',
    artifact: '死亡之蔑',
    artifactImage: '/static/artifacts-guide/artifacts/6054_死亡之蔑_3609.jpg',
    evaluation: '需要搭配专属强化【叠上叠】越拖后期数值越恐怖，让狗头安稳站场无限叠技能',
  },
  {
    hero: '佐伊',
    heroImage: '/static/artifacts-guide/heroes/3164_佐伊_s8_zoe.png',
    artifact: '枯萎宝珠',
    artifactImage: '/static/artifacts-guide/artifacts/6083_枯萎珠宝_blighting_jewel.jpg',
    evaluation: '搭配【双重气泡】佐伊一次丢俩气泡，两个目标同时减魔抗，对面魔抗直接清零，还能疯狂给佐伊回蓝',
  },
  {
    hero: '悠米',
    heroImage: '/static/artifacts-guide/heroes/2151_悠米_s8_yuumi.png',
    artifact: '卢登',
    artifactImage: '/static/artifacts-guide/artifacts/6071_卢登的激荡_luden_s_tempest.jpg',
    evaluation: '搭配【猫之精准】版本无解收割猫！猫之精准直接解锁技能暴击，高额暴击配合卢登过量伤害连锁溅射',
  },
  {
    hero: '莎弥拉',
    heroImage: '/static/artifacts-guide/heroes/4147_莎弥拉_s8_samira.png',
    artifact: '鱼骨头',
    artifactImage: '/static/artifacts-guide/artifacts/6069_鱼骨头_fishbones.jpg',
    evaluation: '搭配英雄强化【评级与交火】大幅缩短大招循环间隔，成型后几乎不间断释放大范围扫射',
  },
  {
    hero: '菲奥娜',
    heroImage: '/static/artifacts-guide/heroes/2146_菲奥娜_s8_fiora.png',
    artifact: '巨型九头蛇',
    artifactImage: '/static/artifacts-guide/artifacts/6090_巨型九头蛇_titanichydra.jpg',
    evaluation: '自带减伤与普攻吸血机制完美契合巨型九头蛇，兼顾坦度、续航与群体输出，对面一堆人围殴都打不残她',
  },
  {
    hero: '塔莉垭',
    heroImage: '/static/artifacts-guide/heroes/4141_塔莉垭_s8_taliyah.png',
    artifact: '卢登',
    artifactImage: '/static/artifacts-guide/artifacts/6071_卢登的激荡_luden_s_tempest.jpg',
    evaluation: '简直是肉坦玩家的噩梦，敌方堆再多血量护甲都扛不住岩雀增伤加成',
  },
  {
    hero: '卑尔维斯',
    heroImage: '/static/artifacts-guide/heroes/4144_卑尔维斯_s8_belveth.png',
    artifact: '连指手套',
    artifactImage: '/static/artifacts-guide/artifacts/6070_连指手套_mittens.jpg',
    evaluation: '攻速还能无限叠加，越残输出越高、回血越猛，全程站场无限输出',
  },
  {
    hero: '莎弥拉',
    heroImage: '/static/artifacts-guide/heroes/4147_莎弥拉_s8_samira.png',
    artifact: '狙击手的专注',
    artifactImage: '/static/artifacts-guide/artifacts/6063_狙击手的专注_2097.jpg',
    evaluation: '远程能同时压制后排与扎堆敌人。只要拉开安全输出距离，每发子弹都能吃到全额伤害增幅',
  },
  {
    hero: '贾克斯',
    heroImage: '/static/artifacts-guide/heroes/3168_贾克斯_s8_jax.png',
    artifact: '恶火小斧',
    artifactImage: '/static/artifacts-guide/artifacts/6096_恶火小斧_hellfirehatchet.jpg',
    evaluation: '搭配专属强化【无情连打】，贾克斯越残攻击越快，血量越低输出越恐怖，简直就是可怕',
  },
  {
    hero: '卡莎',
    heroImage: '/static/artifacts-guide/heroes/3170_卡莎_s8_kaisa.png',
    artifact: '烁刃',
    artifactImage: '/static/artifacts-guide/artifacts/6087_烁刃_flickerblade.jpg',
    evaluation: '搭配专属强化【多重射击】，搭配烁刃无限叠加攻速、双属性加成，全场弹体到处乱飞，非常有视觉效果',
  },
  {
    hero: '薇恩',
    heroImage: '/static/artifacts-guide/heroes/3159_薇恩_s8_vayne.png',
    artifact: '斯塔缇克电刃',
    artifactImage: '/static/artifacts-guide/artifacts/6088_斯塔缇克电刃_statikkshiv.jpg',
    evaluation: '同时打三个目标，全部附带高额真实伤害，再配合电刃三下一次大范围连锁电击，敌方前排再厚的护甲魔抗都扛不住真实伤害',
  },
];

const grid = document.querySelector('#artifactGuideGrid');

function createCard(item) {
  const card = document.createElement('article');
  card.className = 'artifact-guide-card';

  const imageGrid = document.createElement('div');
  imageGrid.className = 'artifact-guide-image-grid';

  const heroWrap = document.createElement('div');
  heroWrap.className = 'artifact-guide-image-wrap';
  const heroImage = document.createElement('img');
  heroImage.className = 'artifact-guide-hero-image';
  heroImage.src = item.heroImage;
  heroImage.alt = item.hero;
  heroImage.loading = 'lazy';
  heroImage.decoding = 'async';
  heroWrap.append(heroImage);

  const artifactWrap = document.createElement('div');
  artifactWrap.className = 'artifact-guide-image-wrap';
  const artifactImage = document.createElement('img');
  artifactImage.className = 'artifact-guide-artifact-image';
  artifactImage.src = item.artifactImage;
  artifactImage.alt = item.artifact;
  artifactImage.loading = 'lazy';
  artifactImage.decoding = 'async';
  artifactWrap.append(artifactImage);

  imageGrid.append(heroWrap, artifactWrap);

  const body = document.createElement('div');
  body.className = 'artifact-guide-body';

  const label = document.createElement('p');
  label.className = 'artifact-guide-label';
  label.textContent = '神器搭配';

  const title = document.createElement('h2');
  title.textContent = `${item.hero} + ${item.artifact}`;

  const evaluation = document.createElement('p');
  evaluation.className = 'artifact-guide-evaluation';
  evaluation.textContent = item.evaluation;

  body.append(label, title, evaluation);
  card.append(imageGrid, body);
  return card;
}

if (grid) {
  grid.replaceChildren(...ARTIFACT_GUIDE_CARDS.map(createCard));
}
