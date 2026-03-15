"""Streamlit artifact renderers for agent status and intelligence reports."""

import pandas as pd
import streamlit as st

_DOMAIN_EMOJI: dict[str, str] = {
    "Market & Trends": "📈",
    "Competitive Intel": "⚔️",
    "Win / Loss": "🎯",
    "Pricing Intel": "💰",
    "Positioning": "📣",
    "Adjacent Markets": "🌐",
}


def render_agent_status(agent_results: list[dict]) -> None:
    """Render a row of metric cards — one per domain agent."""
    cols = st.columns(len(agent_results))
    for col, result in zip(cols, agent_results):
        domain = result.get("domain", result.get("agent", "Agent"))
        emoji = _DOMAIN_EMOJI.get(domain, "🔍")
        signal_count = len(result.get("findings", []))
        error = result.get("error")
        label = f"{emoji} {domain}"
        if error:
            col.metric(label, "Error", delta="✗", delta_color="inverse")
        else:
            col.metric(label, f"{signal_count} signals")


def _render_signals_chart(findings: list[dict]) -> None:
    """Bar chart: signal count per domain."""
    rows = [{"Domain": f.get("domain", "General")} for f in findings if isinstance(f, dict)]
    if not rows:
        return
    counts = (
        pd.DataFrame(rows)
        .groupby("Domain")
        .size()
        .reset_index(name="Signals")
        .set_index("Domain")
    )
    st.bar_chart(counts, x_label="Domain", y_label="Signals")


def render_report(report: dict) -> None:
    """Render the full intelligence report as inline Streamlit artifacts."""
    summary = report.get("summary", "")
    actions = report.get("recommended_actions", [])
    findings = report.get("top_findings", [])
    normalised = [f if isinstance(f, dict) else {"fact": str(f)} for f in findings]

    if summary:
        st.info(f"**Executive Summary**\n\n{summary}")

    if normalised:
        _render_signals_chart(normalised)

    if actions:
        st.subheader("Recommended Actions")
        for i, action in enumerate(actions, 1):
            st.success(f"**{i}.** {action}")

    if normalised:
        st.subheader("Top Findings")
        by_domain: dict[str, list[dict]] = {}
        for f in normalised:
            by_domain.setdefault(f.get("domain", "General"), []).append(f)

        for domain, domain_findings in by_domain.items():
            emoji = _DOMAIN_EMOJI.get(domain, "🔍")
            st.markdown(f"#### {emoji} {domain}")
            for finding in domain_findings:
                fact = finding.get("fact", "")
                source_url = finding.get("source_url", "").strip()
                source_label = finding.get("source_label") or source_url

                with st.expander(fact[:120] + ("…" if len(fact) > 120 else "")):
                    st.write(finding.get("interpretation", ""))
                    if source_url:
                        st.markdown(f"🔗 **Source:** [{source_label}]({source_url})")
                    else:
                        st.caption("⚠️ No source URL provided")
