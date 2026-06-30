from unittest.mock import AsyncMock, patch

from council.pipeline import run_analysis


@patch("council.pipeline.compile_council_graph")
@patch("council.pipeline.store_analysis_results", new_callable=AsyncMock)
@patch("council.pipeline.RedditCollector")
@patch("council.pipeline.HNCollector")
async def test_pipeline_graceful_degradation_no_api_keys(
    mock_hn, mock_reddit, mock_store, mock_compile
):
    mock_reddit_instance = AsyncMock()
    mock_reddit_instance.collect = AsyncMock(return_value=[])
    mock_reddit.return_value = mock_reddit_instance

    mock_hn_instance = AsyncMock()
    mock_hn_instance.collect = AsyncMock(return_value=[])
    mock_hn.return_value = mock_hn_instance

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "query": "test idea",
            "agent_outputs": [
                {
                    "role": "market_analyst",
                    "content": "TAM: $1B. Growing at 5% CAGR.",
                    "citations": [],
                    "confidence": 0.0,
                },
                {
                    "role": "devils_advocate",
                    "content": "Kill Shot 1: Market too small.",
                    "kill_shots": [{"title": "Small Market"}],
                    "verdict": "Fails.",
                    "forbidden_check_passed": True,
                    "retry_attempted": False,
                    "confidence": 0.0,
                },
            ],
            "divergence_points": [],
            "confidence_score": 65.0,
            "round": 1,
            "reddit_posts": [],
            "hn_stories": [],
            "error": None,
        }
    )
    mock_compile.return_value = mock_graph

    result = await run_analysis("AI-powered dental practice management")

    assert result["query"] == "test idea"
    assert len(result["agent_outputs"]) == 2
    assert result["confidence_score"] == 65.0
    assert result["round"] == 1
    assert result["error"] is None

    mock_store.assert_awaited_once()
    mock_graph.ainvoke.assert_awaited_once()


@patch("council.pipeline.compile_council_graph")
@patch("council.pipeline.store_analysis_results", new_callable=AsyncMock)
@patch("council.pipeline.RedditCollector")
@patch("council.pipeline.HNCollector")
async def test_pipeline_handles_collector_failure(mock_hn, mock_reddit, mock_store, mock_compile):
    mock_reddit_instance = AsyncMock()
    mock_reddit_instance.collect = AsyncMock(side_effect=Exception("Serper API down"))
    mock_reddit.return_value = mock_reddit_instance

    mock_hn_instance = AsyncMock()
    mock_hn_instance.collect = AsyncMock(return_value=[])
    mock_hn.return_value = mock_hn_instance

    mock_graph = AsyncMock()
    mock_graph.ainvoke = AsyncMock(
        return_value={
            "agent_outputs": [],
            "divergence_points": [],
            "confidence_score": 0.0,
            "round": 1,
        }
    )
    mock_compile.return_value = mock_graph

    result = await run_analysis("test")

    assert result["agent_outputs"] == []
    assert result["confidence_score"] == 0.0
