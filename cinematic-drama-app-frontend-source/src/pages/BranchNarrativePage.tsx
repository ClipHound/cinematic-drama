import { ChevronLeft, RefreshCw, Sparkles } from 'lucide-react';
import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { ErrorState, LoadingState } from '../components/PageState';
import { loadBranchNarrative, loadDrama } from '../data/catalog';
import type { BranchNarrative, BranchNarrativeNode, BranchRouteTag, DramaItem } from '../data/catalog';

const ROUTE_COLORS: Record<string, string> = {
  justice: 'from-amber-400/20 to-orange-600/10',
  avarice: 'from-purple-400/20 to-fuchsia-600/10',
  hermit: 'from-teal-400/20 to-emerald-600/10',
  transaction: 'from-slate-400/20 to-zinc-600/10',
  shadow: 'from-indigo-400/20 to-violet-600/10',
  seclusion: 'from-cyan-400/20 to-sky-600/10',
  opening: 'from-stone-400/20 to-neutral-700/10',
};

function routeGradient(tag: string): string {
  const key = tag.split('|')[0] || 'opening';
  return ROUTE_COLORS[key] || ROUTE_COLORS.opening;
}

function routeLabel(routeTags: BranchRouteTag[], tag: string): string {
  const ids = tag.split('|');
  const names = ids.map((id) => {
    const found = routeTags.find((r) => r.id === id);
    return found?.name || id;
  });
  return names.join(' · ');
}

function isEndingNode(node: BranchNarrativeNode): boolean {
  return !node.choices || node.choices.length === 0;
}

export default function BranchNarrativePage() {
  const [searchParams] = useSearchParams();
  const dramaId = searchParams.get('drama') || '';
  const [drama, setDrama] = useState<DramaItem | null>(null);
  const [branchData, setBranchData] = useState<BranchNarrative | null>(null);
  const [currentNodeId, setCurrentNodeId] = useState<string>('');
  const [history, setHistory] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [animatingText, setAnimatingText] = useState(false);
  const [reachedEnding, setReachedEnding] = useState(false);
  const [endingRouteId, setEndingRouteId] = useState('');

  const reload = useCallback(async () => {
    if (!dramaId) {
      setError('缺少剧集 ID 参数');
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [loadedDrama, loadedBranch] = await Promise.all([
        loadDrama(dramaId).catch(() => null),
        loadBranchNarrative(dramaId),
      ]);
      setDrama(loadedDrama);
      setBranchData(loadedBranch);
      setCurrentNodeId(loadedBranch.entry_node);
      setHistory([loadedBranch.entry_node]);
    } catch (err) {
      setError(err instanceof Error ? err.message : '续写支线加载失败');
    } finally {
      setLoading(false);
    }
  }, [dramaId]);

  useEffect(() => {
    void reload();
  }, [reload]);

  useEffect(() => {
    if (!currentNodeId) return;
    setAnimatingText(true);
    const timer = setTimeout(() => setAnimatingText(false), 600);
    return () => clearTimeout(timer);
  }, [currentNodeId]);

  const currentNode: BranchNarrativeNode | null = useMemo(() => {
    if (!branchData || !currentNodeId) return null;
    return branchData.nodes[currentNodeId] || null;
  }, [branchData, currentNodeId]);

  const activeRouteTags = useMemo(() => {
    if (!currentNode) return [];
    return currentNode.route_tag.split('|').filter(Boolean);
  }, [currentNode]);

  const handleChoice = useCallback(
    (leadsTo: string) => {
      if (!branchData || !leadsTo || animatingText) return;
      const nextNode = branchData.nodes[leadsTo];

      // leads_to may reference an "ending_<route_tag>" ID instead of a node —
      // that means the player has reached a true ending.
      if (!nextNode) {
        if (leadsTo.startsWith('ending_')) {
          const tagId = leadsTo.slice('ending_'.length);
          setEndingRouteId(tagId);
          setReachedEnding(true);
        }
        // If it's neither a node nor an ending ref, silently ignore (data bug)
        return;
      }

      setHistory((prev) => [...prev, leadsTo]);
      setCurrentNodeId(leadsTo);

      if (isEndingNode(nextNode)) {
        setReachedEnding(true);
      }
    },
    [branchData, animatingText],
  );

  const handleRestart = useCallback(() => {
    if (!branchData) return;
    setCurrentNodeId(branchData.entry_node);
    setHistory([branchData.entry_node]);
    setReachedEnding(false);
    setEndingRouteId('');
  }, [branchData]);

  // All hooks must be called before any conditional return (React rules of hooks)
  const maxLayer = useMemo(() => {
    if (!branchData) return 0;
    return Math.max(...Object.values(branchData.nodes).map((n) => n.layer), 0);
  }, [branchData]);

  const resolvedEndingRoute: BranchRouteTag | null = useMemo(() => {
    if (!branchData || !currentNode) return null;
    if (endingRouteId) {
      let route = branchData.route_tags.find((r) => r.id === endingRouteId);
      if (!route) {
        route = branchData.route_tags.find(
          (r) => r.id.startsWith(endingRouteId) || endingRouteId.startsWith(r.id) || r.id.includes(endingRouteId) || endingRouteId.includes(r.id),
        );
      }
      if (route) return route;
    }
    const primaryTag = currentNode.route_tag.split('|')[0];
    return branchData.route_tags.find((r) => r.id === primaryTag) || null;
  }, [branchData, endingRouteId, currentNode]);

  const totalSteps = maxLayer + 1;
  const currentStep = history.length;

  if (loading) return <LoadingState title="正在加载续写支线" />;
  if (error || !branchData || !currentNode)
    return <ErrorState title="续写支线不可用" message={error || '数据不完整'} onAction={reload} />;

  const gradient = routeGradient(currentNode.route_tag);
  const routeTagLabel = routeLabel(branchData.route_tags, currentNode.route_tag);
  const nodeIsEnding = isEndingNode(currentNode) || reachedEnding;

  return (
    <main className="phone-safe relative flex min-h-dvh flex-col bg-black text-white overflow-hidden">
      {/* Animated background */}
      <div className={`absolute inset-0 bg-gradient-to-b ${gradient} transition-colors duration-1000`} />
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,_var(--tw-gradient-stops))] from-white/5 via-transparent to-transparent" />

      {/* Header */}
      <header className="relative z-40 flex h-14 items-center justify-between px-margin-page">
        <Link
          className="icon-button bg-white/10 backdrop-blur text-white"
          to={drama ? `/detail?drama=${dramaId}` : '/home'}
          aria-label="返回"
        >
          <ChevronLeft size={28} />
        </Link>
        <div className="flex items-center gap-2">
          <Sparkles size={16} className="text-primary" />
          <span className="text-label-md text-white/70">AI 续写支线</span>
        </div>
        <div className="w-10" />
      </header>

      {/* Main narrative area */}
      <section className="relative z-30 flex flex-1 flex-col justify-center px-margin-page py-8">
        {/* Route tag badge */}
        {routeTagLabel && (
          <div className="mb-6 flex flex-wrap items-center gap-2">
            {activeRouteTags.map((tag) => {
              const route = branchData.route_tags.find((r) => r.id === tag);
              return (
                <span
                  key={tag}
                  className="rounded-full border border-white/15 bg-white/5 px-3 py-1 text-label-sm text-white/60 backdrop-blur"
                >
                  {route?.name || tag}
                </span>
              );
            })}
          </div>
        )}

        {/* Node title */}
        <h1
          className={`mb-6 text-display-lg-mobile font-bold leading-tight transition-all duration-500 ${
            animatingText ? 'translate-y-2 opacity-0' : 'translate-y-0 opacity-100'
          }`}
        >
          {currentNode.narrative.title}
        </h1>

        {/* Narrative paragraphs */}
        <div className="mb-6 space-y-4">
          {currentNode.narrative.paragraphs.map((paragraph, index) => (
            <p
              key={index}
              className="text-body-sm leading-relaxed text-white/85 transition-all duration-500"
              style={{
                transitionDelay: `${index * 150}ms`,
                transform: animatingText ? 'translateY(12px)' : 'translateY(0)',
                opacity: animatingText ? 0 : 1,
              }}
            >
              {paragraph}
            </p>
          ))}
        </div>

        {/* Scene description */}
        <div className="mb-4 rounded-xl border border-white/10 bg-white/5 p-4 backdrop-blur">
          <p className="mb-2 text-label-sm text-white/50">场景</p>
          <p className="text-body-sm leading-relaxed text-white/70">{currentNode.narrative.scene_description}</p>
        </div>

        {/* Characters & Mood */}
        <div className="flex flex-wrap gap-4 text-label-sm text-white/50">
          {currentNode.narrative.characters_present.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5">
              <span>出场：</span>
              {currentNode.narrative.characters_present.map((char) => (
                <span key={char} className="rounded-full bg-white/10 px-2 py-0.5 text-white/65">
                  {char}
                </span>
              ))}
            </div>
          )}
          {currentNode.narrative.mood && (
            <div className="flex items-center gap-1.5">
              <span>氛围：</span>
              <span className="italic text-white/65">{currentNode.narrative.mood}</span>
            </div>
          )}
        </div>

        {/* Audio hint */}
        {currentNode.audio_hint && (
          <div className="mt-4 flex flex-wrap gap-3 text-label-sm text-white/35">
            {currentNode.audio_hint.bgm_mood && <span>🎵 {currentNode.audio_hint.bgm_mood}</span>}
            {currentNode.audio_hint.sfx_suggestion && <span>🔊 {currentNode.audio_hint.sfx_suggestion}</span>}
          </div>
        )}
      </section>

      {/* Bottom section: choices or ending */}
      <section className="relative z-30 px-margin-page pb-8 pt-4">
        {nodeIsEnding ? (
          /* Ending screen */
          <div className="rounded-2xl border border-primary/30 bg-black/60 p-6 backdrop-blur-xl animate-[fadeInUp_0.6s_ease-out]">
            <div className="mb-5 text-center">
              <Sparkles size={40} className="mx-auto mb-4 text-primary" />
              <p className="mb-1 text-label-sm text-primary/70">AI 续写 · 结局达成</p>
              <h2 className="mb-3 text-display-lg font-bold">
                {resolvedEndingRoute ? resolvedEndingRoute.name : routeTagLabel}
              </h2>
              {resolvedEndingRoute && (
                <div className="space-y-2 rounded-xl bg-white/5 px-4 py-3 text-left">
                  <p className="text-label-sm text-white/50">🎯 路线主题</p>
                  <p className="text-body-sm leading-relaxed text-white/80">{resolvedEndingRoute.theme}</p>
                  <div className="mt-2 border-t border-white/8 pt-2">
                    <p className="text-label-sm text-white/50">💫 情感弧线</p>
                    <p className="text-body-sm leading-relaxed text-white/70">{resolvedEndingRoute.emotion_arc}</p>
                  </div>
                </div>
              )}
              <p className="mt-3 text-label-sm text-white/40">
                历经 {history.length} 次抉择，抵达此结局
              </p>
            </div>
            <div className="flex gap-3">
              <button
                className="flex flex-1 items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 py-3 text-body-sm text-white/80 backdrop-blur transition active:scale-95"
                type="button"
                onClick={handleRestart}
              >
                <RefreshCw size={18} />
                重新体验
              </button>
              <Link
                className="primary-gradient flex flex-1 items-center justify-center gap-2 rounded-xl py-3 text-body-sm font-semibold text-white transition active:scale-95"
                to={drama ? `/detail?drama=${dramaId}` : '/home'}
              >
                返回剧集
              </Link>
            </div>
          </div>
        ) : (
          /* Choice buttons */
          <div className="space-y-3">
            <p className="mb-2 text-label-sm text-white/45">做出你的选择：</p>
            {currentNode.choices.map((choice, index) => (
              <button
                key={choice.choice_id}
                className={`w-full rounded-2xl border border-white/15 bg-white/5 p-4 text-left backdrop-blur transition-all duration-300 hover:border-primary/40 hover:bg-white/10 active:scale-[0.98] ${
                  animatingText ? 'translate-y-4 opacity-0' : 'translate-y-0 opacity-100'
                }`}
                style={{ transitionDelay: `${300 + index * 120}ms` }}
                type="button"
                onClick={() => handleChoice(choice.leads_to)}
                disabled={animatingText}
              >
                <p className="mb-1 text-body-lg font-semibold text-white/90">{choice.option_text}</p>
                <p className="text-label-md text-white/50">{choice.option_subtext}</p>
              </button>
            ))}
          </div>
        )}

        {/* Progress bar — shows depth progress, not total nodes across all branches */}
        <div className="mt-4 flex items-center gap-2">
          <div className="h-0.5 flex-1 rounded-full bg-white/10">
            <div
              className="h-full rounded-full bg-primary/50 transition-all duration-700"
              style={{ width: `${Math.round((currentStep / totalSteps) * 100)}%` }}
            />
          </div>
          <span className="text-label-sm text-white/30">
            {nodeIsEnding ? `${currentStep}/${totalSteps} · 完` : `${currentStep}/${totalSteps}`}
          </span>
        </div>
      </section>
    </main>
  );
}
