import { Bot, Send, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { Link } from 'react-router-dom';
import BottomNav from '../components/BottomNav';
import { requestAiSearch } from '../data/catalog';
import type { AiSearchResult } from '../data/catalog';

type Message = {
  role: 'user' | 'assistant';
  text: string;
  results?: AiSearchResult[];
};

const starters = ['我想看扮猪吃虎爽剧', '找有互动打脸点的剧', '下一集可能怎么反转？'];

function resultHref(result: AiSearchResult) {
  if (result.type === 'episode' && result.episodeNumber) {
    return `/player?drama=${result.dramaId}&episode=${result.episodeNumber}`;
  }
  return `/detail?drama=${result.dramaId}`;
}

export default function AiSearchPage() {
  const [input, setInput] = useState('');
  const [pending, setPending] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      text: '我可以按题材、情绪点、互动类型帮你找剧。比如：想看高燃打脸，或者想找有剧情预测卡的集数。',
    },
  ]);

  const submit = async (text = input) => {
    const value = text.trim();
    if (!value || pending) return;
    setMessages((old) => [...old, { role: 'user', text: value }]);
    setInput('');
    setPending(true);
    try {
      const result = await requestAiSearch(value);
      setMessages((old) => [
        ...old,
        {
          role: 'assistant',
          text: result.results.length ? `找到 ${result.results.length} 个相关结果。` : '没有找到匹配内容，换个剧情点再试。',
          results: result.results,
        },
      ]);
    } catch (err) {
      setMessages((old) => [
        ...old,
        {
          role: 'assistant',
          text: err instanceof Error ? err.message : 'AI 搜索服务暂时不可用。',
          results: [],
        },
      ]);
    } finally {
      setPending(false);
    }
  };

  return (
    <main className="phone-safe flex min-h-dvh flex-col pb-24 pt-5">
      <header className="px-margin-page pb-4">
        <p className="text-label-md text-primary">沉浸式对话</p>
        <h1 className="text-display-lg font-bold">AI 搜索</h1>
      </header>

      <section className="hide-scrollbar flex-1 space-y-3 overflow-y-auto px-margin-page">
        {messages.map((message, index) => (
          <div key={`${message.role}-${index}`} className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}>
            <div
              className={`max-w-[88%] rounded-2xl px-4 py-3 text-body-sm ${
                message.role === 'user' ? 'bg-primary-container text-white' : 'glass-panel text-on-surface'
              }`}
            >
              {message.role === 'assistant' ? (
                <span className="mb-1 flex items-center gap-1 text-label-md text-primary">
                  <Bot size={14} />
                  剧场 AI
                </span>
              ) : null}
              <p className="leading-relaxed">{message.text}</p>
              {message.results?.length ? (
                <div className="mt-3 grid gap-2">
                  {message.results.map((result) => (
                    <Link
                      key={`${result.type}-${result.dramaId}-${result.episodeNumber || 'detail'}`}
                      className="rounded-xl border border-white/8 bg-white/6 p-3 text-left transition active:scale-[0.99]"
                      to={resultHref(result)}
                    >
                      <span className="mb-1 inline-flex rounded-full bg-primary/15 px-2 py-0.5 text-label-sm text-primary">
                        {result.type === 'episode' ? `第 ${result.episodeNumber} 集` : '剧目'}
                      </span>
                      <strong className="block text-body-lg text-on-surface">{result.title}</strong>
                      {result.snippet || result.subtitle ? (
                        <span className="line-clamp-3 text-body-sm text-on-surface-variant">{result.snippet || result.subtitle}</span>
                      ) : null}
                    </Link>
                  ))}
                </div>
              ) : null}
            </div>
          </div>
        ))}

        <div className="grid gap-2 py-2">
          {starters.map((starter) => (
            <button
              key={starter}
              className="glass-panel flex items-center gap-2 rounded-2xl px-3 py-2 text-left text-label-md"
              type="button"
              onClick={() => submit(starter)}
            >
              <Sparkles size={14} className="text-primary" />
              {starter}
            </button>
          ))}
        </div>
      </section>

      <footer className="fixed bottom-[70px] left-1/2 z-40 flex w-full max-w-[430px] -translate-x-1/2 gap-2 bg-background/80 px-margin-page py-3 backdrop-blur-2xl">
        <input
          className="glass-panel h-12 min-w-0 flex-1 rounded-2xl border-white/10 bg-white/5 px-4 text-body-sm text-on-surface placeholder:text-on-surface-variant focus:ring-1 focus:ring-primary"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          placeholder="描述你想看的剧情"
          onKeyDown={(event) => {
            if (event.key === 'Enter') submit();
          }}
        />
        <button className="primary-gradient grid h-12 w-12 place-items-center rounded-2xl text-white disabled:opacity-60" type="button" onClick={() => submit()} disabled={pending}>
          <Send size={18} />
        </button>
      </footer>

      <BottomNav />
    </main>
  );
}
