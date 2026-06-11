import { Bot, ChevronRight, Clock3, Loader2, Play, Search, Send, Sparkles } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { streamAiChat } from '../data/catalog';
import type { AiChatMessageInput, AiChatMode, AiRecommendation } from '../data/catalog';

type Message = {
  id: string;
  role: 'user' | 'assistant';
  text: string;
  recommendations?: AiRecommendation[];
  error?: string;
  progress?: string[];
};

type ChatHistoryItem = {
  id: string;
  title: string;
  updatedAt: number;
  userText: string;
  assistantText: string;
};

const CHAT_HISTORY_KEY = 'ai-search-chat-history-v1';

const starters = ['短剧为什么容易让人上头？', '找古装权谋爽剧', '帮我分析复仇题材的爽点', '推荐能直接播放的高燃片段'];

function createId(prefix: string) {
  return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function createWelcomeMessage(): Message {
  return {
    id: 'welcome',
    role: 'assistant',
    text: '你可以直接问我问题、聊短剧，也可以让我推荐可播放内容。',
  };
}

function loadChatHistory(): ChatHistoryItem[] {
  try {
    const raw = window.localStorage.getItem(CHAT_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    if (!Array.isArray(parsed)) return [];
    const normalized = parsed
      .map(normalizeHistoryItem)
      .filter((item): item is ChatHistoryItem => Boolean(item));
    const seen = new Set<string>();
    return normalized
      .sort((left, right) => right.updatedAt - left.updatedAt)
      .filter((item) => {
        const key = item.userText.trim();
        if (seen.has(key)) return false;
        seen.add(key);
        return true;
      })
      .slice(0, 3);
  } catch {
    return [];
  }
}

function compactHistoryText(value: string, maxLength = 96) {
  const compacted = value.replace(/\s+/g, ' ').trim();
  return compacted.length > maxLength ? `${compacted.slice(0, maxLength)}...` : compacted;
}

function historyTitle(userText: string) {
  const title = userText.trim() || '最近记录';
  return title.length > 18 ? `${title.slice(0, 18)}...` : title;
}

function normalizeHistoryItem(item: unknown): ChatHistoryItem | null {
  if (!item || typeof item !== 'object') return null;
  const record = item as Partial<ChatHistoryItem> & { messages?: Message[] };
  const legacyMessages = Array.isArray(record.messages) ? record.messages : [];
  const userText = typeof record.userText === 'string'
    ? record.userText
    : [...legacyMessages].reverse().find((message) => message.role === 'user')?.text || '';
  const assistantText = typeof record.assistantText === 'string'
    ? record.assistantText
    : [...legacyMessages].reverse().find((message) => message.role === 'assistant' && message.text.trim())?.text || '';
  if (!userText.trim()) return null;
  return {
    id: typeof record.id === 'string' ? record.id : createId('history'),
    title: typeof record.title === 'string' ? record.title : historyTitle(userText),
    updatedAt: typeof record.updatedAt === 'number' ? record.updatedAt : Date.now(),
    userText: compactHistoryText(userText, 48),
    assistantText: compactHistoryText(assistantText),
  };
}

function saveChatHistoryItem(item: ChatHistoryItem) {
  const current = loadChatHistory().filter((history) => history.id !== item.id && history.userText !== item.userText);
  const next = [item, ...current].sort((left, right) => right.updatedAt - left.updatedAt).slice(0, 3);
  window.localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(next));
  return next;
}

function safeHref(value: string) {
  return value.startsWith('/player') || value.startsWith('/detail') ? value : '/search';
}

function safeDisplayReason(item: AiRecommendation) {
  const reason = item.reason?.trim();
  if (!reason || /(相似度|关键词匹配|评分|score|分数|embedding|向量|检索)/i.test(reason)) {
    return item.type === 'episode' ? '这集更贴近你想看的剧情节奏。' : '题材和剧情方向更贴近你的需求。';
  }
  return reason;
}

function RecommendationCard({ item }: { item: AiRecommendation }) {
  const href = safeHref(item.href);
  return (
    <Link className="flex gap-3 rounded-xl border border-white/8 bg-white/6 p-3 text-left transition active:scale-[0.99]" to={href}>
      <img className="h-24 w-16 shrink-0 rounded-lg object-cover" src={item.imageUrl} alt={item.title} />
      <span className="min-w-0 flex-1">
        <span className="mb-1 inline-flex rounded-full bg-primary/15 px-2 py-0.5 text-label-sm text-primary">
          {item.type === 'episode' && item.episodeNumber ? `第 ${item.episodeNumber} 集` : '剧目'}
        </span>
        <strong className="line-clamp-1 text-body-lg text-on-surface">{item.title}</strong>
        {item.subtitle ? <span className="line-clamp-1 text-label-md text-on-surface-variant">{item.subtitle}</span> : null}
        <span className="line-clamp-2 pt-1 text-body-sm text-on-surface-variant">{safeDisplayReason(item)}</span>
        <span className="mt-2 inline-flex items-center gap-1 text-label-md text-primary">
          <Play size={13} fill="currentColor" />
          {item.type === 'episode' ? '播放剧集' : '查看详情'}
        </span>
      </span>
      <ChevronRight size={17} className="mt-9 shrink-0 text-on-surface-variant" />
    </Link>
  );
}

function safeMarkdownHref(value: string) {
  if (value.startsWith('/') || value.startsWith('https://') || value.startsWith('http://')) return value;
  return '#';
}

function renderInlineMarkdown(text: string, prefix: string) {
  const nodes: ReactNode[] = [];
  const codeMark = String.fromCharCode(96);
  const pattern = new RegExp(
    '(' + codeMark + '[^' + codeMark + ']+' + codeMark + '|\\*\\*[^*]+\\*\\*|\\*[^*]+\\*|\\[[^\\]]+\\]\\(([^)\\s]+)\\))',
    'g',
  );
  let cursor = 0;
  for (const match of text.matchAll(pattern)) {
    const token = match[0];
    const tokenIndex = match.index ?? 0;
    if (tokenIndex > cursor) nodes.push(text.slice(cursor, tokenIndex));
    if (token.startsWith('**')) {
      nodes.push(<strong key={prefix + '-strong-' + tokenIndex} className="font-semibold text-on-surface">{token.slice(2, -2)}</strong>);
    } else if (token.startsWith('*')) {
      nodes.push(<em key={prefix + '-em-' + tokenIndex}>{token.slice(1, -1)}</em>);
    } else if (token.startsWith(codeMark)) {
      nodes.push(
        <code key={prefix + '-code-' + tokenIndex} className="rounded bg-white/10 px-1 py-0.5 text-[0.9em] text-primary">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      const linkMatch = token.match(/^\[([^\]]+)\]\(([^)]+)\)$/);
      if (linkMatch) {
        const href = safeMarkdownHref(linkMatch[2]);
        nodes.push(
          <a
            key={prefix + '-link-' + tokenIndex}
            className="text-primary underline underline-offset-4"
            href={href}
            rel={href.startsWith('http') ? 'noreferrer' : undefined}
            target={href.startsWith('http') ? '_blank' : undefined}
          >
            {linkMatch[1]}
          </a>,
        );
      }
    }
    cursor = tokenIndex + token.length;
  }
  if (cursor < text.length) nodes.push(text.slice(cursor));
  return nodes;
}

function MarkdownText({ text }: { text: string }) {
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  let index = 0;

  while (index < lines.length) {
    const line = lines[index];
    if (!line.trim()) {
      index += 1;
      continue;
    }

    const heading = line.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      const levelClass = heading[1].length === 1 ? 'text-body-lg' : 'text-body-md';
      blocks.push(
        <p key={'heading-' + index} className={levelClass + ' font-semibold leading-relaxed text-on-surface'}>
          {renderInlineMarkdown(heading[2], 'heading-' + index)}
        </p>,
      );
      index += 1;
      continue;
    }

    const ordered = line.match(/^\s*\d+[.)]\s+(.+)$/);
    const unordered = line.match(/^\s*[-*]\s+(.+)$/);
    if (ordered || unordered) {
      const isOrdered = Boolean(ordered);
      const items: ReactNode[] = [];
      while (index < lines.length) {
        const itemMatch = isOrdered ? lines[index].match(/^\s*\d+[.)]\s+(.+)$/) : lines[index].match(/^\s*[-*]\s+(.+)$/);
        if (!itemMatch) break;
        items.push(
          <li key={'item-' + index} className="pl-1">
            {renderInlineMarkdown(itemMatch[1], 'item-' + index)}
          </li>,
        );
        index += 1;
      }
      const ListTag = isOrdered ? 'ol' : 'ul';
      blocks.push(
        <ListTag key={'list-' + index} className={(isOrdered ? 'list-decimal' : 'list-disc') + ' space-y-1 pl-5 leading-relaxed'}>
          {items}
        </ListTag>,
      );
      continue;
    }

    const paragraphLines: string[] = [];
    while (index < lines.length) {
      const current = lines[index];
      if (!current.trim()) break;
      if (/^(#{1,3})\s+/.test(current) || /^\s*(\d+[.)]|[-*])\s+/.test(current)) break;
      paragraphLines.push(current);
      index += 1;
    }
    blocks.push(
      <p key={'paragraph-' + index} className="whitespace-pre-wrap leading-relaxed">
        {renderInlineMarkdown(paragraphLines.join('\n'), 'paragraph-' + index)}
      </p>,
    );
  }

  return <div className="space-y-2">{blocks}</div>;
}

function MessageBubble({
  message,
  active,
}: {
  message: Message;
  active: boolean;
}) {
  const isUser = message.role === 'user';
  return (
    <div className={`flex ${isUser ? 'justify-end' : 'justify-start'}`}>
      <div
        className={`max-w-[92%] rounded-2xl px-4 py-3 text-body-sm ${
          isUser ? 'bg-primary-container text-white' : 'glass-panel text-on-surface'
        } ${message.recommendations?.length ? 'w-full' : ''}`}
      >
        {!isUser ? (
          <span className="mb-1 flex items-center gap-1 text-label-md text-primary">
            <Bot size={14} />
            剧场 AI
          </span>
        ) : null}
        {message.text ? (
          isUser ? (
            <p className="whitespace-pre-wrap leading-relaxed">{message.text}</p>
          ) : (
            <MarkdownText text={message.text} />
          )
        ) : null}
        {message.error ? <p className="rounded-xl bg-error/10 px-3 py-2 text-label-md text-error">{message.error}</p> : null}
        {active && message.progress?.length ? (
          <div className="mt-2 grid gap-1 rounded-xl bg-white/6 px-3 py-2 text-label-md text-on-surface-variant">
            {message.progress.map((item, index) => (
              <span key={item + index} className="inline-flex items-center gap-2">
                <Loader2 size={12} className={index === message.progress!.length - 1 ? 'animate-spin text-primary' : 'text-primary'} />
                {item}
              </span>
            ))}
          </div>
        ) : null}
        {message.recommendations?.length ? (
          <div className="mt-3 grid gap-2">
            {message.recommendations.map((item) => (
              <RecommendationCard key={item.id} item={item} />
            ))}
          </div>
        ) : null}
      </div>
    </div>
  );
}

export default function AiSearchPage() {
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [chatMode, setChatMode] = useState<AiChatMode>('fast');
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const [historyItems, setHistoryItems] = useState<ChatHistoryItem[]>(() => loadChatHistory());
  const [messages, setMessages] = useState<Message[]>([createWelcomeMessage()]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  const updateAssistant = (assistantId: string, update: (message: Message) => Message) => {
    setMessages((current) => current.map((message) => (message.id === assistantId ? update(message) : message)));
  };

  const persistChatTurn = (userText: string, assistantMessage?: Message) => {
    const assistantText = assistantMessage?.text.trim() || (assistantMessage?.recommendations?.length ? '已返回推荐内容' : '');
    if (!userText.trim() || !assistantText) return;
    const nextHistory = saveChatHistoryItem({
      id: createId('history'),
      title: historyTitle(userText),
      updatedAt: Date.now(),
      userText: compactHistoryText(userText, 48),
      assistantText: compactHistoryText(assistantText),
    });
    setHistoryItems(nextHistory);
  };

  const submit = async (text = input) => {
    const value = text.trim();
    if (!value || pending) return;

    const userMessage: Message = { id: createId('user'), role: 'user', text: value };
    const assistantId = createId('assistant');
    const assistantMessage: Message = { id: assistantId, role: 'assistant', text: '', progress: ['正在思考'] };
    const nextMessages = [...messages, userMessage, assistantMessage];
    setMessages(nextMessages);
    setInput('');
    setPending(true);
    let queuedRecommendations: AiRecommendation[] = [];

    const requestMessages: AiChatMessageInput[] = [...messages, userMessage]
      .filter((message) => message.text.trim())
      .slice(-8)
      .map((message) => ({ role: message.role, content: message.text }));

    try {
      await streamAiChat(requestMessages, (event) => {
        if (event.type === 'progress') {
          updateAssistant(assistantId, (message) => ({ ...message, progress: [...(message.progress || []), event.message].slice(-4) }));
        } else 
        if (event.type === 'tool_call_start') {
          updateAssistant(assistantId, (message) => ({ ...message, progress: [...(message.progress || []), event.query ? '正在查找：' + event.query : '正在查找可播放内容'].slice(-4) }));
        } else if (event.type === 'tool_call_result') {
          updateAssistant(assistantId, (message) => ({ ...message, progress: [...(message.progress || []), event.count ? '正在整理回复' : '正在生成回复'].slice(-4) }));
        } else if (event.type === 'recommendations') {
          queuedRecommendations = event.items.slice(0, 3);
        } else if (event.type === 'text_delta') {
          updateAssistant(assistantId, (message) => ({ ...message, text: `${message.text}${event.text}` }));
        } else if (event.type === 'error') {
          updateAssistant(assistantId, (message) => ({ ...message, error: event.message }));
        } else if (event.type === 'message_end') {
          if (queuedRecommendations.length) {
            updateAssistant(assistantId, (message) => ({ ...message, recommendations: queuedRecommendations, progress: undefined }));
          }
          setMessages((current) => {
            const finished = current.map((message) => (message.id === assistantId ? { ...message, recommendations: queuedRecommendations.length ? queuedRecommendations : message.recommendations, progress: undefined } : message));
            persistChatTurn(value, finished.find((message) => message.id === assistantId));
            return finished;
          });
          setPending(false);
        }
      }, { mode: chatMode });
    } catch (err) {
      updateAssistant(assistantId, (message) => ({
        ...message,
        error: err instanceof Error ? err.message : 'AI 搜索服务暂时不可用。',
        progress: undefined,
      }));
    } finally {
      setPending(false);
    }
  };

  const activeAssistantId = pending ? [...messages].reverse().find((message) => message.role === 'assistant')?.id : null;

  return (
    <main className="phone-safe flex min-h-dvh flex-col pb-24 pt-5">
      <header className="px-margin-page pb-4">
        <p className="text-label-md text-primary">智能对话与按需检索</p>
        <div className="flex items-center justify-between gap-3">
          <h1 className="text-display-lg font-bold">AI 搜索</h1>
          <Link className="rounded-full bg-white/8 px-3 py-2 text-label-md text-on-surface-variant" to="/search">
            普通搜索
          </Link>
        </div>
        <div className="mt-3 flex items-center gap-2">
          <div className="inline-flex rounded-full bg-white/8 p-1 text-label-md">
            <button
              className={`rounded-full px-3 py-1.5 ${chatMode === 'fast' ? 'bg-primary text-white' : 'text-on-surface-variant'}`}
              type="button"
              onClick={() => setChatMode('fast')}
              disabled={pending}
            >
              快速
            </button>
            <button
              className={`rounded-full px-3 py-1.5 ${chatMode === 'smart' ? 'bg-primary text-white' : 'text-on-surface-variant'}`}
              type="button"
              onClick={() => setChatMode('smart')}
              disabled={pending}
            >
              智能
            </button>
          </div>
        </div>
        {historyItems.length ? (
          <div className="mt-3 rounded-2xl bg-white/6 px-3 py-2">
            <div className="mb-2 flex items-center gap-1 text-label-md text-on-surface-variant">
              <Clock3 size={13} />
              最近记录
            </div>
            <div className="grid gap-2">
              {historyItems.map((item) => (
                <div key={item.id} className="rounded-xl bg-black/10 px-3 py-2">
                  <p className="line-clamp-1 text-label-md text-on-surface">{item.userText}</p>
                  {item.assistantText ? <p className="line-clamp-2 text-label-md text-on-surface-variant">{item.assistantText}</p> : null}
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </header>

      <section ref={scrollRef} className="hide-scrollbar flex-1 space-y-3 overflow-y-auto px-margin-page pb-3">
        {messages.map((message) => (
          <MessageBubble key={message.id} message={message} active={message.id === activeAssistantId} />
        ))}

        <div className="grid gap-2 py-2">
          {starters.map((starter) => (
            <button
              key={starter}
              className="glass-panel flex items-center gap-2 rounded-2xl px-3 py-2 text-left text-label-md disabled:opacity-60"
              type="button"
              onClick={() => void submit(starter)}
              disabled={pending}
            >
              <Sparkles size={14} className="text-primary" />
              {starter}
            </button>
          ))}
        </div>
      </section>

      <footer className="fixed bottom-[70px] left-1/2 z-40 flex w-full max-w-[430px] -translate-x-1/2 gap-2 bg-background/80 px-margin-page py-3 backdrop-blur-2xl">
        <label className="glass-panel flex h-12 min-w-0 flex-1 items-center gap-2 rounded-2xl border-white/10 bg-white/5 px-3">
          <Search size={16} className="shrink-0 text-on-surface-variant" />
          <input
            className="min-w-0 flex-1 border-0 bg-transparent p-0 text-body-sm text-on-surface placeholder:text-on-surface-variant focus:ring-0"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            placeholder="提问、聊天或找一部短剧"
            onKeyDown={(event) => {
              if (event.key === 'Enter') void submit();
            }}
            disabled={pending}
          />
        </label>
        <button className="primary-gradient grid h-12 w-12 place-items-center rounded-2xl text-white disabled:opacity-60" type="button" onClick={() => void submit()} disabled={pending}>
          {pending ? <Loader2 size={18} className="animate-spin" /> : <Send size={18} />}
        </button>
      </footer>

      <BottomNav />
    </main>
  );
}
