"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Header from "@/components/Header";
import "./style.css";

export default function DashboardPage() {
  const [user, setUser] = useState<Record<string, unknown> | null>(null);
  const router = useRouter();

  useEffect(() => {
    const raw = localStorage.getItem("session");
    if (!raw) { router.replace("/profile"); return; }
    setUser(JSON.parse(raw));
  }, [router]);

  if (!user) return null;

  return (
    <main className="dashboard" aria-label="知识库中台仪表盘">
      <div className="dashboard-inner">
        <Header user={user} />

        <section className="stats" aria-label="顶部指标">
          <article className="stat has-icon">
            <div className="stat-icon" aria-hidden="true">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                <path d="m12 3 8 4.4-8 4.4-8-4.4L12 3Z" stroke="currentColor" strokeWidth="2"/>
                <path d="m4 12 8 4.4 8-4.4M4 16.6 12 21l8-4.4" stroke="currentColor" strokeWidth="2" strokeLinecap="round"/>
              </svg>
            </div>
            <div className="stat-title">知识库总数</div>
            <div className="stat-value">128</div>
            <div className="spark" aria-hidden="true">
              <svg viewBox="0 0 116 28">
                <polyline points="0,24 15,9 29,15 44,10 60,6 75,20 91,12 106,4" fill="none" stroke="#2d75ff" strokeWidth="1.5"/>
                <g fill="#2d75ff"><circle cx="15" cy="9" r="1.8"/><circle cx="44" cy="10" r="1.8"/><circle cx="75" cy="20" r="1.8"/><circle cx="106" cy="4" r="1.8"/></g>
              </svg>
            </div>
          </article>

          <article className="stat">
            <div className="stat-title">内存使用</div>
            <div className="stat-value"><span>72</span><span>%</span></div>
            <div className="ring" style={{ "--p": 72, "--ring": "#2d75ff" } as React.CSSProperties}><b>72%</b></div>
            <div className="mini-note"><span>使用 36.9GB / 51.2GB</span></div>
            <div className="metric-line" style={{ "--w": "72%", "--c": "#2d75ff" } as React.CSSProperties}><span /></div>
          </article>

          <article className="stat">
            <div className="stat-title">今日新增</div>
            <div className="stat-value">18</div>
            <span className="up" aria-hidden="true" />
            <div className="spark" aria-hidden="true">
              <svg viewBox="0 0 116 28">
                <polyline points="0,18 14,13 28,16 42,10 56,18 70,9 84,12 98,20 112,8" fill="none" stroke="#20c784" strokeWidth="1.5"/>
                <g fill="#20c784"><circle cx="0" cy="18" r="1.7"/><circle cx="28" cy="16" r="1.7"/><circle cx="70" cy="9" r="1.7"/><circle cx="112" cy="8" r="1.7"/></g>
              </svg>
            </div>
          </article>

          <article className="stat">
            <div className="stat-title">索引完成率</div>
            <div className="stat-value"><span>96</span><span>%</span></div>
            <div className="ring" style={{ "--p": 96, "--ring": "#2fc287" } as React.CSSProperties}><b>96%</b></div>
            <div className="mini-note"><span>已完成 96%</span></div>
            <div className="metric-line" style={{ "--w": "96%", "--c": "#28c383" } as React.CSSProperties}><span /></div>
          </article>

          <article className="stat calls">
            <div className="stat-title">调用次数</div>
            <div className="stat-value">12.8万</div>
            <div className="call-note"><span>较昨日</span><span className="positive">↑ 18.6%</span></div>
            <div className="bars" aria-hidden="true">
              <span style={{ "--h": "14px" } as React.CSSProperties} />
              <span style={{ "--h": "21px" } as React.CSSProperties} />
              <span style={{ "--h": "33px" } as React.CSSProperties} />
              <span style={{ "--h": "18px" } as React.CSSProperties} />
              <span style={{ "--h": "26px" } as React.CSSProperties} />
              <span style={{ "--h": "17px" } as React.CSSProperties} />
              <span style={{ "--h": "29px" } as React.CSSProperties} />
            </div>
          </article>
        </section>

        <section className="cards" aria-label="知识库分类">
          <article className="library-card left">
            <div className="library-head">
              <span className="library-icon" aria-hidden="true">
                <svg width="23" height="23" viewBox="0 0 24 24" fill="none">
                  <path d="M5 3h11l3 3v15H5V3Z" fill="#2d75ff"/>
                  <path d="M16 3v4h4" fill="#98c0ff"/>
                  <path d="M8 11h8M8 15h6" stroke="white" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
              </span>
              <div>
                <div className="library-title">文档知识库</div>
                <div className="accent" />
              </div>
            </div>
            <div className="label">文档</div>
            <div className="count">8,462</div>
            <div className="visual" aria-hidden="true">
              <div className="stage" />
              <div className="doc-stack">
                <span className="doc-sheet" />
                <span className="doc-sheet" />
                <span className="doc-sheet" />
              </div>
            </div>
            <div className="info">
              <div className="row">
                <span className="mini-icon">
                  <svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="M2 3h8v6H2V3Zm1-1h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
                </span>
                <span>存储空间</span>
                <strong>128.7 GB</strong>
              </div>
              <div className="row">
                <span className="mini-icon">
                  <svg width="9" height="9" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6 3.5v3L8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg>
                </span>
                <span>更新时间</span>
                <strong>2024-05-21 14:30</strong>
              </div>
              <div className="row">
                <span className="mini-icon">
                  <svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="m2.5 6.3 2.1 2.1 4.9-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg>
                </span>
                <span>完成率</span>
                <div className="progress"><span style={{ width: "94%" }} /></div>
                <strong>94%</strong>
              </div>
            </div>
            <a className="more" href="/detail?type=documents">查看详情 <span>→</span></a>
          </article>

          <article className="library-card center">
            <div className="library-head">
              <span className="library-icon" aria-hidden="true">
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="4" width="18" height="16" rx="3" fill="#15bfb6"/>
                  <path d="m10 8 6 4-6 4V8Z" fill="white"/>
                </svg>
              </span>
              <div>
                <div className="library-title">视频知识库</div>
                <div className="accent" />
              </div>
            </div>
            <div className="label">视频</div>
            <div className="count">326</div>
            <div className="visual" aria-hidden="true">
              <div className="stage" />
              <span className="cube c" />
              <div className="video-stack">
                <div className="film" />
                <div className="video-pane"><span className="play" /></div>
              </div>
            </div>
            <div className="info">
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="M2 3h8v6H2V3Zm1-1h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg></span>
                <span>存储空间</span>
                <strong>256.4 GB</strong>
              </div>
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6 3.5v3L8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg></span>
                <span>更新时间</span>
                <strong>2024-05-21 14:45</strong>
              </div>
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="m2.5 6.3 2.1 2.1 4.9-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
                <span>完成率</span>
                <div className="progress"><span style={{ width: "97%", background: "#20c7be" }} /></div>
                <strong>97%</strong>
              </div>
            </div>
            <a className="more" href="/detail?type=videos">查看详情 <span>→</span></a>
          </article>

          <article className="library-card right">
            <div className="library-head">
              <span className="library-icon" aria-hidden="true">
                <svg width="23" height="23" viewBox="0 0 24 24" fill="none">
                  <rect x="3" y="4" width="18" height="16" rx="3" fill="#416bff"/>
                  <path d="m6.5 17 4.2-5.2 3.1 3.6 1.8-2.2L20 17H6.5Z" fill="white"/>
                  <circle cx="15.8" cy="9" r="1.5" fill="#dbe7ff"/>
                </svg>
              </span>
              <div>
                <div className="library-title">图片知识库</div>
                <div className="accent" />
              </div>
            </div>
            <div className="label">图片</div>
            <div className="count">1,284</div>
            <div className="visual" aria-hidden="true">
              <div className="stage" />
              <span className="cube a" />
              <span className="cube b" />
              <div className="img-stack">
                <div className="img-pane" />
                <div className="img-pane" />
                <div className="img-pane"><span className="sun" /><span className="mountain" /></div>
              </div>
            </div>
            <div className="info">
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="M2 3h8v6H2V3Zm1-1h6" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg></span>
                <span>存储空间</span>
                <strong>96.3 GB</strong>
              </div>
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><circle cx="6" cy="6" r="4.5" stroke="currentColor" strokeWidth="1.2"/><path d="M6 3.5v3L8 8" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/></svg></span>
                <span>更新时间</span>
                <strong>2024-05-21 14:20</strong>
              </div>
              <div className="row">
                <span className="mini-icon"><svg width="9" height="9" viewBox="0 0 12 12" fill="none"><path d="m2.5 6.3 2.1 2.1 4.9-5" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/></svg></span>
                <span>完成率</span>
                <div className="progress"><span style={{ width: "92%" }} /></div>
                <strong>92%</strong>
              </div>
            </div>
            <a className="more" href="/detail?type=images">查看详情 <span>→</span></a>
          </article>
        </section>
      </div>
    </main>
  );
}
