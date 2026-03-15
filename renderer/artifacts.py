"""Streamlit artifact renderers for agent status and intelligence reports."""

import streamlit as st

_DOMAIN_EMOJI: dict[str, str] = {
    "Market & Trends": "📈",
    "Competitive Intel": "⚔️",
    "Win / Loss": "🎯",
    "Pricing Intel": "💰",
    "Positioning": "📣",
    "Adjacent Markets": "🌐",
}

_CONFIDENCE_BADGE: dict[str, str] = {
    "high": "🟢 High",
    "medium": "🟡 Medium",
    "low": "🔴 Low",
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


def render_report(report: dict) -> None:
    """Render the full intelligence report as inline Streamlit artifacts."""
    summary = report.get("summary", "")
    actions = report.get("recommended_actions", [])
    findings = report.get("top_findings", [])

    if summary:
        st.info(f"**Executive Summary**\n\n{summary}")

    if actions:
        st.subheader("Recommended Actions")
        for i, action in enumerate(actions, 1):
            st.success(f"**{i}.** {action}")

    if findings:
        st.subheader("Top Findings")
        # Normalise: ensure each finding is a dict (handles Pydantic model_dump output)
        normalised = [f if isinstance(f, dict) else {"fact": str(f)} for f in findings]
        by_domain: dict[str, list[dict]] = {}
        for f in normalised:
            domain = f.get("domain", "General")
            by_domain.setdefault(domain, []).append(f)

        for domain, domain_findings in by_domain.items():
            emoji = _DOMAIN_EMOJI.get(domain, "🔍")
            st.markdown(f"#### {emoji} {domain}")
            for finding in domain_findings:  # type: ignore[assignment]
                fact = finding.get("fact", "")
                interpretation = finding.get("interpretation", "")
                confidence = finding.get("confidence", "medium")
                source_url = finding.get("source_url")
                source_label = finding.get("source_label", source_url)
                badge = _CONFIDENCE_BADGE.get(confidence, "🟡 Medium")

                with st.expander(fact[:120] + ("…" if len(fact) > 120 else "")):
                    st.write(interpretation)
                    st.caption(f"Confidence: {badge}")
                    if source_url:
                        st.markdown(f"[{source_label}]({source_url})")
