import { useMemo, useState } from 'react';
import { ChevronLeft, Heart, MessageCircle, Plus, Search, Star, Wifi } from 'lucide-react';
import FactionCheerOverlay, {
  type FactionData,
  type UserCheerAction,
} from './components/FactionCheerOverlay';

import './App.css';

function App() {
  const [leftScore, setLeftScore] = useState(126_380);
  const [rightScore, setRightScore] = useState(117_240);
  const [userAction, setUserAction] = useState<UserCheerAction>({
    selectedFactionId: 'blue',
    cheerCount: 27,
    contribution: 27,
  });
  const [liked, setLiked] = useState(false);
  const [following, setFollowing] = useState(false);
  const [favorited, setFavorited] = useState(false);

  const totalScore = leftScore + rightScore;

  const leftFaction = useMemo<FactionData>(
    () => ({
      id: 'red',
      name: '红方阵营',
      color: '#ff3b35',
      score: leftScore,
      percent: Math.round((leftScore / totalScore) * 100),
      character: {
        url: '/assets/hero-left.png',
        scale: 1,
        offsetX: 0,
        offsetY: 0,
        facing: 'right',
      },
    }),
    [leftScore, totalScore],
  );

  const rightFaction = useMemo<FactionData>(
    () => ({
      id: 'blue',
      name: '蓝方阵营',
      color: '#2f80ff',
      score: rightScore,
      percent: 100 - Math.round((leftScore / totalScore) * 100),
      character: {
        url: '/assets/hero-right.png',
        scale: 1,
        offsetX: 0,
        offsetY: 0,
        facing: 'left',
      },
    }),
    [leftScore, rightScore, totalScore],
  );

  const selectFaction = (id: string) => {
    setUserAction((current) => ({
      selectedFactionId: id,
      cheerCount: current.selectedFactionId === id ? current.cheerCount : current.cheerCount,
      contribution: current.contribution,
    }));
  };

  const cheerForFaction = (id: string) => {
    setUserAction((current) => ({
      selectedFactionId: id,
      cheerCount: current.cheerCount + 1,
      contribution: current.contribution + 1,
    }));

    if (id === leftFaction.id) {
      setLeftScore((score) => score + 1);
    } else {
      setRightScore((score) => score + 1);
    }
  };

  return (
    <main className="app-shell" aria-label="短剧推荐助威页">
      <section className="phone-screen">
        <div className="scene-bg" aria-hidden="true">
          <div className="scene-noise" />
          <img className="hero hero-left" src="/assets/hero-left.png" alt="" draggable={false} />
          <img className="hero hero-right" src="/assets/hero-right.png" alt="" draggable={false} />
          <div className="hero-split" />
          <div className="scene-vignette" />
        </div>

        <header className="status-bar" aria-label="状态栏">
          <span className="status-time">9:41</span>
          <div className="status-icons" aria-hidden="true">
            <span className="signal-bars">
              <i />
              <i />
              <i />
              <i />
            </span>
            <Wifi size={25} strokeWidth={3} />
            <span className="battery">
              <span />
            </span>
          </div>
        </header>

        <nav className="top-nav" aria-label="短剧频道">
          <button className="app-icon-button back-button" type="button" aria-label="返回">
            <ChevronLeft size={51} strokeWidth={1.9} />
          </button>
          <div className="tabs" role="tablist" aria-label="频道切换">
            <button className="tab" type="button" role="tab" aria-selected="false">
              追剧
            </button>
            <button className="tab tab-active" type="button" role="tab" aria-selected="true">
              推荐
            </button>
            <button className="tab" type="button" role="tab" aria-selected="false">
              找剧
            </button>
          </div>
          <button className="app-icon-button search-button" type="button" aria-label="搜索">
            <Search size={49} strokeWidth={1.9} />
          </button>
        </nav>

        <aside className="side-actions" aria-label="视频操作">
          <button
            className={`author-action ${following ? 'is-active' : ''}`}
            type="button"
            aria-label={following ? '已追剧' : '追剧'}
            aria-pressed={following}
            onClick={() => setFollowing((value) => !value)}
          >
            <span className="author-ring">
              <span className="author-avatar" />
            </span>
            {!following && (
              <span className="author-plus">
                <Plus size={20} strokeWidth={3} />
              </span>
            )}
            <span className="side-label">{following ? '已追' : '追剧'}</span>
          </button>
          <button
            className={`side-action ${liked ? 'like-active' : ''}`}
            type="button"
            aria-label="点赞 12.6万"
            aria-pressed={liked}
            onClick={() => setLiked((value) => !value)}
          >
            <Heart className="filled-icon" size={52} strokeWidth={liked ? 0 : 2.2} />
            <span>{liked ? '12.7万' : '12.6万'}</span>
          </button>
          <button className="side-action" type="button" aria-label="评论 3421">
            <MessageCircle className="filled-icon" size={50} strokeWidth={0} />
            <span>3421</span>
          </button>
          <button
            className={`side-action ${favorited ? 'star-active' : ''}`}
            type="button"
            aria-label={favorited ? '已追剧收藏' : '追剧收藏'}
            aria-pressed={favorited}
            onClick={() => setFavorited((value) => !value)}
          >
            <Star className="filled-icon" size={54} strokeWidth={favorited ? 0 : 2.2} />
            <span>{favorited ? '已追' : '追剧'}</span>
          </button>
        </aside>

        <FactionCheerOverlay
          visible
          state="cheering"
          timerText="00:05:27"
          promptText="选择阵营，为TA助威"
          leftFaction={leftFaction}
          rightFaction={rightFaction}
          compositeCharacterImage="/assets/duel-characters.png"
          userAction={userAction}
          onSelectFaction={selectFaction}
          onCheer={cheerForFaction}
          onOpenRecord={() => {
            console.log('open cheer record');
          }}
        />
      </section>
    </main>
  );
}

export default App;
