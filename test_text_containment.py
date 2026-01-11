"""Tests for the graph layout lane assignment algorithm."""

import pytest
import git
from octotui.graph_layout import GraphLayoutEngine


class TestLaneAssignment:
    """Test suite for lane assignment algorithm."""
    
    @pytest.fixture
    def repo(self):
        """Get the current git repository."""
        return git.Repo(".")
    
    @pytest.fixture
    def graph(self, repo):
        """Build a graph from the current repository."""
        engine = GraphLayoutEngine(repo)
        return engine.build_graph(max_commits=50)
    
    def test_graph_builds_successfully(self, graph):
        """Test that the graph builds without errors."""
        assert graph is not None
        assert len(graph.commits) > 0
    
    def test_all_commits_have_valid_lanes(self, graph):
        """Test that all commits have non-negative lane assignments."""
        for commit in graph.commits.values():
            assert commit.lane >= 0, f"Commit {commit.short_sha} has invalid lane {commit.lane}"
    
    def test_max_lanes_is_positive(self, graph):
        """Test that max_lanes is at least 1."""
        assert graph.max_lanes >= 1
    
    def test_lane_assignments_within_max(self, graph):
        """Test that no commit has a lane >= max_lanes."""
        for commit in graph.commits.values():
            assert commit.lane < graph.max_lanes, (
                f"Commit {commit.short_sha} has lane {commit.lane} >= max_lanes {graph.max_lanes}"
            )
    
    def test_active_lanes_populated(self, graph):
        """Test that active_lanes is populated for each commit."""
        commits = graph.get_commits_in_order()
        for commit in commits:
            # active_lanes should be a set (may be empty for initial commits)
            assert isinstance(commit.active_lanes, set)
    
    def test_color_index_assigned(self, graph):
        """Test that color_index is assigned based on lane."""
        for commit in graph.commits.values():
            expected_color = commit.lane % len(graph.colors)
            assert commit.color_index == expected_color, (
                f"Commit {commit.short_sha} has color_index {commit.color_index}, "
                f"expected {expected_color} for lane {commit.lane}"
            )
    
    def test_merge_commits_have_merge_source_lanes(self, graph):
        """Test that merge commits with multiple parents in graph have merge_source_lanes."""
        for commit in graph.commits.values():
            if commit.is_merge():
                # Count parents that are in our graph
                parents_in_graph = [
                    p for p in commit.parent_shas if graph.get_commit(p)
                ]
                if len(parents_in_graph) > 1:
                    # Should have merge_source_lanes or the lanes converged
                    # (merge_source_lanes may be empty if all parents have same lane)
                    assert isinstance(commit.merge_source_lanes, list)
    
    def test_edges_have_valid_lanes(self, graph):
        """Test that all edges have valid from_lane and to_lane."""
        for edge in graph.edges:
            assert edge.from_lane >= 0, f"Edge has invalid from_lane {edge.from_lane}"
            assert edge.to_lane >= 0, f"Edge has invalid to_lane {edge.to_lane}"


class TestGraphLayoutEngine:
    """Test suite for GraphLayoutEngine class."""
    
    @pytest.fixture
    def repo(self):
        """Get the current git repository."""
        return git.Repo(".")
    
    def test_engine_initialization(self, repo):
        """Test that engine initializes correctly."""
        engine = GraphLayoutEngine(repo)
        assert engine.repo == repo
        assert engine.graph is not None
    
    def test_build_graph_returns_commit_graph(self, repo):
        """Test that build_graph returns a CommitGraph."""
        engine = GraphLayoutEngine(repo)
        graph = engine.build_graph(max_commits=10)
        from octotui.graph_data import CommitGraph
        assert isinstance(graph, CommitGraph)
    
    def test_build_graph_respects_max_commits(self, repo):
        """Test that build_graph respects max_commits limit."""
        engine = GraphLayoutEngine(repo)
        graph = engine.build_graph(max_commits=5)
        assert len(graph.commits) <= 5
    
    def test_empty_repo_handling(self, tmp_path):
        """Test that engine handles empty repos gracefully."""
        # Create a new empty repo
        empty_repo = git.Repo.init(tmp_path)
        engine = GraphLayoutEngine(empty_repo)
        graph = engine.build_graph(max_commits=10)
        # Should not crash, just have no commits
        assert len(graph.commits) == 0
        assert graph.max_lanes == 1
