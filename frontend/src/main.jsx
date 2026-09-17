import React, {
  useEffect,
  useState,
} from "react";

import { createRoot } from "react-dom/client";

import "./style.css";


function App() {
  const [q, setQ] = useState("");
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(false);

  const [file, setFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [uploadResult, setUploadResult] = useState(null);

  const [documents, setDocuments] = useState([]);
  const [documentsLoading, setDocumentsLoading] = useState(true);

  const [analytics, setAnalytics] = useState(null);
  const [analyticsLoading, setAnalyticsLoading] = useState(false);

  const [evaluation, setEvaluation] = useState(null);
  const [evaluationLoading, setEvaluationLoading] = useState(false);

  const [
    evaluationEvaluatedAt,
    setEvaluationEvaluatedAt,
  ] = useState(null);

  const [history, setHistory] = useState([]);
  const [historyLoading, setHistoryLoading] = useState(false);

  const [systemState, setSystemState] = useState('starting');

  useEffect(() => {
    let interval;
    const checkReady = async () => {
      try {
        const res = await fetch('/api/ready');
        if (res.ok) {
          setSystemState('ready');
        } else if (res.status === 503) {
          setSystemState('warming');
        } else {
          setSystemState('temporarily unavailable');
        }
      } catch (e) {
        setSystemState('temporarily unavailable');
      }
    };
    checkReady();
    interval = setInterval(checkReady, 5000);
    return () => clearInterval(interval);
  }, []);


  // ========================================================
  // DOCUMENTS
  // ========================================================

  async function loadDocuments() {
    setDocumentsLoading(true);

    try {
      const response = await fetch("/api/documents");

      if (!response.ok) {
        throw new Error(
          "API returned " + response.status
        );
      }

      const result = await response.json();

      setDocuments(
        Array.isArray(result)
          ? result
          : []
      );
    } catch (error) {
      console.error(
        "Failed to load documents:",
        error
      );
    } finally {
      setDocumentsLoading(false);
    }
  }


  // ========================================================
  // HISTORY
  // ========================================================

  async function loadHistory() {
    setHistoryLoading(true);

    try {
      const response = await fetch("/api/history");

      if (!response.ok) {
        throw new Error(
          "History API returned " +
          response.status
        );
      }

      const result = await response.json();

      setHistory(
        Array.isArray(result)
          ? result
          : []
      );
    } catch (error) {
      console.error(
        "Failed to load query history:",
        error
      );
    } finally {
      setHistoryLoading(false);
    }
  }


  // ========================================================
  // ANALYTICS
  // ========================================================

  async function loadAnalytics() {
    setAnalyticsLoading(true);

    try {
      const response = await fetch("/api/analytics");

      if (!response.ok) {
        throw new Error(
          "Analytics API returned " +
          response.status
        );
      }

      const result = await response.json();

      setAnalytics(result);
    } catch (error) {
      console.error(
        "Failed to load analytics:",
        error
      );
    } finally {
      setAnalyticsLoading(false);
    }
  }


  // ========================================================
  // INITIAL LOAD
  // ========================================================

  useEffect(() => {
    loadDocuments();
    loadHistory();
    loadAnalytics();
  }, []);


  // ========================================================
  // ASK
  // ========================================================

  async function ask() {
    const question = q.trim();

    if (!question || loading) {
      return;
    }

    setLoading(true);
    setData(null);

    try {
      const response = await fetch(
        "/api/query",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          body: JSON.stringify({
            question,
          }),
        }
      );

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const reqId = response.headers.get("x-request-id") || result?.detail?.request_id || "";
        const msg = result?.detail?.message || result?.detail || "Query failed";
        const suffix = reqId ? ` (Request ID: ${reqId})` : "";
        throw new Error(msg + suffix);
      }

      setData(result);

      await Promise.all([
        loadHistory(),
        loadAnalytics(),
      ]);
    } catch (error) {
      console.error(
        "Query failed:",
        error
      );

      setData({
        answer:
          error.message ||
          "API connection failed.",

        confidence: "low",

        citations: [],

        diagnostics: null,

        retrieved: [],
      });
    } finally {
      setLoading(false);
    }
  }


  // ========================================================
  // UPLOAD
  // ========================================================

  async function uploadDocument() {
    if (!file || uploading) {
      return;
    }

    setUploading(true);
    setUploadResult(null);

    try {
      const formData = new FormData();

      formData.append(
        "file",
        file
      );

      const response = await fetch(
        "/api/ingest",
        {
          method: "POST",
          body: formData,
        }
      );

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const reqId = response.headers.get("x-request-id") || result?.detail?.request_id || "";
        const msg = result?.detail?.message || result?.detail || "Upload failed";
        const suffix = reqId ? ` (Request ID: ${reqId})` : "";
        throw new Error(msg + suffix);
      }

      setUploadResult({
        success: true,

        message:
          result.filename +
          " indexed successfully. " +
          result.chunks +
          " chunk" +
          (
            result.chunks === 1
              ? ""
              : "s"
          ) +
          " created.",
      });

      setFile(null);

      const input =
        document.getElementById(
          "document-input"
        );

      if (input) {
        input.value = "";
      }

      await loadDocuments();
    } catch (error) {
      console.error(
        "Upload failed:",
        error
      );

      setUploadResult({
        success: false,

        message:
          error.message ||
          "Upload failed.",
      });
    } finally {
      setUploading(false);
    }
  }


  // ========================================================
  // DELETE DOCUMENT
  // ========================================================

  async function deleteDocument(
    documentId,
    filename
  ) {
    const confirmed =
      window.confirm(
        'Delete "' +
        filename +
        '" from the knowledge base?'
      );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        "/api/documents/" +
        encodeURIComponent(documentId),
        {
          method: "DELETE",
        }
      );

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const reqId = response.headers.get("x-request-id") || result?.detail?.request_id || "";
        const msg = result?.detail?.message || result?.detail || "Delete failed";
        const suffix = reqId ? ` (Request ID: ${reqId})` : "";
        throw new Error(msg + suffix);
      }

      setDocuments(
        (current) =>
          current.filter(
            (doc) =>
              doc.document_id !==
              documentId
          )
      );

      setData(null);

      await loadAnalytics();
    } catch (error) {
      console.error(
        "Delete failed:",
        error
      );

      alert(
        error.message ||
        "Delete failed."
      );
    }
  }


  // ========================================================
  // CLEAR HISTORY
  // ========================================================

  async function clearHistory() {
    if (history.length === 0) {
      return;
    }

    const confirmed =
      window.confirm(
        "Clear all query history?"
      );

    if (!confirmed) {
      return;
    }

    try {
      const response = await fetch(
        "/api/history",
        {
          method: "DELETE",
        }
      );

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const reqId = response.headers.get("x-request-id") || result?.detail?.request_id || "";
        const msg = result?.detail?.message || result?.detail || "Failed to clear history";
        const suffix = reqId ? ` (Request ID: ${reqId})` : "";
        throw new Error(msg + suffix);
      }

      setHistory([]);

      await loadAnalytics();
    } catch (error) {
      console.error(
        "Failed to clear history:",
        error
      );

      alert(
        error.message ||
        "Failed to clear history."
      );
    }
  }


  // ========================================================
  // EVALUATION
  // ========================================================

  async function runEvaluation() {
    if (evaluationLoading) {
      return;
    }

    setEvaluationLoading(true);
    setEvaluation(null);

    try {
      const response =
        await fetch(
          "/api/evaluation"
        );

      const result = await response.json().catch(() => ({}));

      if (!response.ok) {
        const reqId = response.headers.get("x-request-id") || result?.detail?.request_id || "";
        const msg = result?.detail?.message || result?.detail || "Evaluation failed";
        const suffix = reqId ? ` (Request ID: ${reqId})` : "";
        throw new Error(msg + suffix);
      }

      setEvaluation(result);

      setEvaluationEvaluatedAt(
        new Date()
      );
    } catch (error) {
      console.error(
        "Evaluation failed:",
        error
      );

      setEvaluation({
        status: "error",

        error:
          error.message ||
          "Evaluation failed.",
      });
    } finally {
      setEvaluationLoading(false);
    }
  }


  // ========================================================
  // KEYBOARD
  // ========================================================

  function handleKeyDown(event) {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      ask();
    }
  }


  // ========================================================
  // HELPERS
  // ========================================================

  function hasValue(value) {
    return (
      value !== null &&
      value !== undefined &&
      Number.isFinite(
        Number(value)
      )
    );
  }


  function metricPercent(value) {
    if (!hasValue(value)) {
      return "N/A";
    }

    return (
      Number(value) * 100
    ).toFixed(2) + "%";
  }


  function metricNumber(
    value,
    digits = 4
  ) {
    if (!hasValue(value)) {
      return "N/A";
    }

    return Number(value).toFixed(digits);
  }


  function latencyValue(value) {
    if (!hasValue(value)) {
      return "N/A";
    }

    return (
      Number(value).toFixed(0) +
      " ms"
    );
  }


  function metricPass(
    value,
    threshold,
    mode = "min"
  ) {
    if (
      !hasValue(value) ||
      !hasValue(threshold)
    ) {
      return false;
    }

    if (mode === "max") {
      return (
        Number(value) <=
        Number(threshold)
      );
    }

    return (
      Number(value) >=
      Number(threshold)
    );
  }


  function progressPercent(
    value,
    multiplier = 100
  ) {
    if (!hasValue(value)) {
      return 0;
    }

    return Math.max(
      0,
      Math.min(
        100,
        Number(value) * multiplier
      )
    );
  }


  // ========================================================
  // DERIVED STATE
  // ========================================================

  const diagnostics =
    data?.diagnostics;

  const totalChunks =
    documents.reduce(
      (sum, doc) =>
        sum +
        Number(
          doc.chunks || 0
        ),
      0
    );

  const evaluationPassed =
    evaluation?.status ===
    "passed";

  const evaluationMetrics =
    evaluation?.metrics || {};

  const evaluationBenchmarks =
    evaluation?.benchmarks || {};


  const recallAt1Pass =
    metricPass(
      evaluationMetrics.recall_at_1,
      evaluationBenchmarks.minimum_recall_at_1
    );


  const recallAtKPass =
    hasValue(
      evaluationMetrics.recall_at_k
    ) &&
    Number(
      evaluationMetrics.recall_at_k
    ) >= 0.8;


  const mrrPass =
    metricPass(
      evaluationMetrics.mrr,
      evaluationBenchmarks.minimum_mrr
    );


  const citationPass =
    hasValue(
      evaluationMetrics.citation_correctness
    ) &&
    Number(
      evaluationMetrics.citation_correctness
    ) >= 0.8;


  const groundingPass =
    hasValue(
      evaluationMetrics.answer_grounding
    ) &&
    Number(
      evaluationMetrics.answer_grounding
    ) >= 0.8;


  const abstentionPass =
    hasValue(
      evaluationMetrics.abstention_accuracy
    ) &&
    Number(
      evaluationMetrics.abstention_accuracy
    ) >= 0.8;


  const latencyTargetMs =
    Number(
      evaluationBenchmarks
        .maximum_warm_latency_seconds ?? 0
    ) * 1000;


  const latencyPass =
    metricPass(
      evaluationMetrics.warm_latency_ms,
      latencyTargetMs,
      "max"
    );


  const qualityMetrics = [
    {
      key: "recall_at_1",

      label: "Recall@1",

      value:
        metricPercent(
          evaluationMetrics.recall_at_1
        ),

      target:
        evaluationBenchmarks.minimum_recall_at_1 !==
        undefined
          ? "Target ≥ " +
            (
              Number(
                evaluationBenchmarks
                  .minimum_recall_at_1
              ) * 100
            ).toFixed(0) +
            "%"
          : "Target unavailable",

      progress:
        progressPercent(
          evaluationMetrics.recall_at_1
        ),

      passed: recallAt1Pass,
    },

    {
      key: "recall_at_k",

      label:
        "Recall@" +
        (
          evaluationBenchmarks.recall_k ||
          "K"
        ),

      value:
        metricPercent(
          evaluationMetrics.recall_at_k
        ),

      target:
        "Expected source found in top-K",

      progress:
        progressPercent(
          evaluationMetrics.recall_at_k
        ),

      passed: recallAtKPass,
    },

    {
      key: "mrr",

      label: "MRR",

      value:
        metricNumber(
          evaluationMetrics.mrr
        ),

      target:
        evaluationBenchmarks.minimum_mrr !==
        undefined
          ? "Target ≥ " +
            Number(
              evaluationBenchmarks.minimum_mrr
            ).toFixed(2)
          : "Target unavailable",

      progress:
        progressPercent(
          evaluationMetrics.mrr
        ),

      passed: mrrPass,
    },

    {
      key: "citation_correctness",

      label: "Citation Correctness",

      value:
        metricPercent(
          evaluationMetrics.citation_correctness
        ),

      target:
        "Expected source cited",

      progress:
        progressPercent(
          evaluationMetrics.citation_correctness
        ),

      passed: citationPass,
    },

    {
      key: "answer_grounding",

      label: "Answer Grounding",

      value:
        metricPercent(
          evaluationMetrics.answer_grounding
        ),

      target:
        "Required evidence terms",

      progress:
        progressPercent(
          evaluationMetrics.answer_grounding
        ),

      passed: groundingPass,
    },

    {
      key: "abstention_accuracy",

      label: "Abstention Accuracy",

      value:
        metricPercent(
          evaluationMetrics.abstention_accuracy
        ),

      target:
        "Unknown questions rejected",

      progress:
        progressPercent(
          evaluationMetrics.abstention_accuracy
        ),

      passed: abstentionPass,
    },
  ];


  const qualityScoreValues = [
    evaluationMetrics.recall_at_1,
    evaluationMetrics.recall_at_k,
    evaluationMetrics.mrr,
    evaluationMetrics.citation_correctness,
    evaluationMetrics.answer_grounding,
    evaluationMetrics.abstention_accuracy,
  ].filter(hasValue);


  const overallQualityScore =
    qualityScoreValues.length > 0
      ? (
          qualityScoreValues.reduce(
            (sum, value) =>
              sum + Number(value),
            0
          ) /
          qualityScoreValues.length
        ) * 100
      : null;


  const overallQualityLabel =
    overallQualityScore === null
      ? "N/A"
      : overallQualityScore >= 95
        ? "Excellent"
        : overallQualityScore >= 85
          ? "Strong"
          : overallQualityScore >= 75
            ? "Good"
            : "Needs Improvement";


  const overallQualityClass =
    overallQualityScore === null
      ? ""
      : overallQualityScore >= 85
        ? "strong"
        : overallQualityScore >= 75
          ? "good"
          : "needs-work";


  // ========================================================
  // RENDER
  // ========================================================

  return (
    <main className="app">
      {systemState !== 'ready' && (
        <div className={`status-banner ${systemState}`}>
          System Status: {systemState.toUpperCase()}
        </div>
      )}

      {/* ==================================================
          HERO
      ================================================== */}

      <header className="hero">

        <div className="badge">
          PRO RAG
        </div>

        <h1>
          Evidence-first
          knowledge assistant
        </h1>

        <p>
          Hybrid retrieval · semantic
          search · reranking · citations
          · abstention
        </p>

      </header>


      {/* ==================================================
          SYSTEM METRICS
      ================================================== */}

      <section className="metrics-grid">

        <div className="metric-card">
          <span>Documents</span>

          <strong>
            {documents.length}
          </strong>
        </div>


        <div className="metric-card">
          <span>Chunks</span>

          <strong>
            {totalChunks}
          </strong>
        </div>


        <div className="metric-card">
          <span>Engine</span>

          <strong>
            Online
          </strong>
        </div>


        <div className="metric-card">
          <span>Grounding</span>

          <strong>
            Enabled
          </strong>
        </div>

      </section>


      {/* ==================================================
          RAG ANALYTICS
      ================================================== */}

      <section className="card analytics-card">

        <div className="section-title">

          <div>

            <h2>
              RAG Analytics
            </h2>

            <p>
              Aggregate performance from
              persisted query history.
            </p>

          </div>


          <button
            className="secondary-button"
            onClick={() => {
              loadAnalytics();
              loadHistory();
            }}
            disabled={analyticsLoading}
          >
            {
              analyticsLoading
                ? "Refreshing..."
                : "Refresh"
            }
          </button>

        </div>


        {!analytics ? (

          <p className="muted">
            Loading analytics...
          </p>

        ) : (

          <div className="analytics-grid">

            <div className="analytics-stat">
              <span>Total Queries</span>

              <strong>
                {analytics.total_queries}
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Grounded Rate</span>

              <strong>
                {
                  Number(
                    analytics.grounded_rate
                  ).toFixed(1)
                }
                %
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Citation Coverage</span>

              <strong>
                {
                  Number(
                    analytics.citation_coverage
                  ).toFixed(1)
                }
                %
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Abstention Rate</span>

              <strong>
                {
                  Number(
                    analytics.abstention_rate
                  ).toFixed(1)
                }
                %
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Avg Latency</span>

              <strong>
                {
                  Number(
                    analytics.average_latency_ms
                  ).toFixed(0)
                }
                ms
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Avg Retrieval</span>

              <strong>
                {
                  Number(
                    analytics.average_retrieval_ms
                  ).toFixed(0)
                }
                ms
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Avg Generation</span>

              <strong>
                {
                  Number(
                    analytics.average_generation_ms
                  ).toFixed(2)
                }
                ms
              </strong>
            </div>


            <div className="analytics-stat">
              <span>Avg Retrieved</span>

              <strong>
                {
                  Number(
                    analytics.average_retrieved_chunks
                  ).toFixed(1)
                }
              </strong>
            </div>

          </div>

        )}

      </section>


      {/* ==================================================
          KNOWLEDGE BASE
      ================================================== */}

      <section className="card">

        <div className="section-title">

          <div>

            <h2>
              Knowledge Base
            </h2>

            <p>
              Upload and manage indexed
              documents.
            </p>

          </div>


          <span className="document-count">

            {documents.length}{" "}

            document
            {
              documents.length === 1
                ? ""
                : "s"
            }

          </span>

        </div>


        <div className="upload-row">

          <input
            id="document-input"
            type="file"
            accept=".pdf,.txt,.md"
            onChange={(event) => {
              setFile(
                event.target.files?.[0] ||
                null
              );

              setUploadResult(null);
            }}
            disabled={uploading}
          />


          <button
            className="secondary-button"
            onClick={uploadDocument}
            disabled={
              !file ||
              uploading
            }
          >
            {
              uploading
                ? "Indexing..."
                : "Upload & Index"
            }
          </button>

        </div>


        {file && (
          <div className="selected-file">
            Selected:{" "}

            <strong>
              {file.name}
            </strong>
          </div>
        )}


        {uploadResult && (
          <div
            className={
              uploadResult.success
                ? "upload-result success"
                : "upload-result error"
            }
          >
            {uploadResult.message}
          </div>
        )}


        <div className="documents">

          <h3>
            Indexed Documents
          </h3>


          {documentsLoading ? (

            <p className="muted">
              Loading documents...
            </p>

          ) : documents.length === 0 ? (

            <p className="muted">
              No documents indexed yet.
            </p>

          ) : (

            documents.map(
              (doc) => (

                <div
                  className="document"
                  key={doc.document_id}
                >

                  <div className="document-info">

                    <strong>
                      {doc.filename}
                    </strong>

                    <span>
                      {doc.chunks} chunk
                      {
                        doc.chunks === 1
                          ? ""
                          : "s"
                      }
                    </span>

                  </div>


                  <button
                    className="danger-button"
                    onClick={() =>
                      deleteDocument(
                        doc.document_id,
                        doc.filename
                      )
                    }
                  >
                    Delete
                  </button>

                </div>

              )
            )

          )}

        </div>

      </section>


      {/* ==================================================
          EVALUATION
      ================================================== */}

      <section className="card">

        <div className="section-title">

          <div>

            <h2>
              Evaluation
            </h2>

            <p>
              Live benchmark of retrieval,
              grounding, citations,
              abstention and latency.
            </p>

          </div>


          <button
            className="secondary-button"
            onClick={runEvaluation}
            disabled={evaluationLoading}
          >
            {
              evaluationLoading
                ? "Running..."
                : "Run Evaluation"
            }
          </button>

        </div>


        {!evaluation &&
          !evaluationLoading && (

            <div className="evaluation-empty">

              <div className="evaluation-empty-icon">
                RAG
              </div>

              <div>

                <strong>
                  Ready for evaluation
                </strong>

                <p>
                  Run the benchmark to
                  validate the current
                  RAG system.
                </p>

              </div>

            </div>

          )}


        {evaluationLoading && (

          <div className="evaluation-running">

            <div className="evaluation-loader">
              <span />
              <span />
              <span />
            </div>

            <div>

              <strong>
                Running evaluation...
              </strong>

              <p>
                Measuring retrieval,
                grounding, citations,
                abstention and latency.
              </p>

            </div>

          </div>

        )}


        {evaluation &&
          evaluation.status !== "error" && (

            <>

              <div
                className={
                  evaluationPassed
                    ? "evaluation-status evaluation-status-passed"
                    : "evaluation-status evaluation-status-failed"
                }
              >

                <div className="evaluation-status-main">

                  <span
                    className={
                      evaluationPassed
                        ? "status-pill passed"
                        : "status-pill failed"
                    }
                  >
                    {
                      evaluationPassed
                        ? "ALL TESTS PASSED"
                        : "EVALUATION FAILED"
                    }
                  </span>


                  {evaluation.report_available && (
                    <span className="report-live">
                      Live metrics
                    </span>
                  )}

                </div>


                <span className="evaluation-summary">

                  {evaluation.tests?.passed ?? 0}
                  {" / "}
                  {evaluation.tests?.total ?? 0}
                  {" tests passed"}

                </span>

              </div>


              <div className="eval-test-strip">

                <div className="eval-test-stat">
                  <span>Passed</span>

                  <strong className="pass-text">
                    {evaluation.tests?.passed ?? 0}
                  </strong>
                </div>


                <div className="eval-test-stat">
                  <span>Failed</span>

                  <strong className="fail-text">
                    {evaluation.tests?.failed ?? 0}
                  </strong>
                </div>


                <div className="eval-test-stat">
                  <span>Skipped</span>

                  <strong>
                    {evaluation.tests?.skipped ?? 0}
                  </strong>
                </div>


                <div className="eval-test-stat">
                  <span>Runtime</span>

                  <strong>
                    {
                      evaluation.duration_seconds ??
                      "N/A"
                    }
                    s
                  </strong>
                </div>

              </div>


              <div className="evaluation-section-heading">

                <h3>
                  RAG Quality Metrics
                </h3>

                <p>
                  Measured directly by the
                  evaluation suite.
                </p>

              </div>


              <div className="evaluation-metrics-grid">

                {qualityMetrics.map(
                  (metric) => (

                    <div
                      className="evaluation-metric-card"
                      key={metric.key}
                    >

                      <div className="evaluation-metric-top">

                        <span className="evaluation-metric-label">
                          {metric.label}
                        </span>


                        <span
                          className={
                            metric.passed
                              ? "metric-result pass"
                              : "metric-result fail"
                          }
                        >
                          {
                            metric.passed
                              ? "PASS"
                              : "CHECK"
                          }
                        </span>

                      </div>


                      <strong className="evaluation-metric-value">
                        {metric.value}
                      </strong>


                      <div className="metric-progress">

                        <div
                          className={
                            metric.passed
                              ? "metric-progress-fill pass"
                              : "metric-progress-fill fail"
                          }
                          style={{
                            width:
                              metric.progress +
                              "%",
                          }}
                        />

                      </div>


                      <span className="evaluation-metric-target">
                        {metric.target}
                      </span>

                    </div>

                  )
                )}

              </div>


              <div className="quality-overview">

                <div className="quality-score-block">

                  <span className="quality-score-label">
                    Overall RAG Quality Score
                  </span>


                  <div className="quality-score-row">

                    <strong>
                      {
                        overallQualityScore !== null
                          ? overallQualityScore.toFixed(1) +
                            "%"
                          : "N/A"
                      }
                    </strong>


                    <span
                      className={
                        "quality-badge " +
                        overallQualityClass
                      }
                    >
                      {overallQualityLabel}
                    </span>

                  </div>


                  <p>
                    Composite of the measured
                    retrieval, citation,
                    grounding and abstention
                    metrics.
                  </p>

                </div>


                <div
                  className="quality-score-ring"
                  style={{
                    "--score":
                      overallQualityScore ?? 0,
                  }}
                >

                  <div className="quality-score-ring-inner">

                    {
                      overallQualityScore !== null
                        ? Math.round(
                            overallQualityScore
                          )
                        : "—"
                    }

                  </div>

                </div>

              </div>


              <div className="latency-panel">

                <div className="latency-primary">

                  <span className="latency-label">
                    Warm Query Latency
                  </span>

                  <strong>
                    {
                      latencyValue(
                        evaluationMetrics
                          .warm_latency_ms
                      )
                    }
                  </strong>

                </div>


                <div className="latency-target">

                  <span>
                    Maximum target
                  </span>

                  <strong>
                    {
                      latencyTargetMs.toFixed(0)
                    }{" "}
                    ms
                  </strong>

                </div>


                <span
                  className={
                    latencyPass
                      ? "metric-result pass"
                      : "metric-result fail"
                  }
                >
                  {
                    latencyPass
                      ? "PASS"
                      : "CHECK"
                  }
                </span>

              </div>


              <div className="benchmark-row">

                <div>

                  <span>
                    Recall@1 minimum
                  </span>

                  <strong>
                    {
                      (
                        Number(
                          evaluationBenchmarks
                            .minimum_recall_at_1 ??
                          0
                        ) * 100
                      ).toFixed(0)
                    }
                    %
                  </strong>

                </div>


                <div>

                  <span>
                    MRR minimum
                  </span>

                  <strong>
                    {
                      Number(
                        evaluationBenchmarks
                          .minimum_mrr ?? 0
                      ).toFixed(2)
                    }
                  </strong>

                </div>


                <div>

                  <span>
                    Recall K
                  </span>

                  <strong>
                    {
                      evaluationBenchmarks
                        .recall_k ??
                      "N/A"
                    }
                  </strong>

                </div>

              </div>


              <div className="evaluation-report">

                <div>

                  <span>
                    Evaluation Report
                  </span>

                  <strong>
                    {
                      evaluation.report_available
                        ? "Generated"
                        : "Unavailable"
                    }
                  </strong>

                </div>


                <span
                  className={
                    evaluation.report_available
                      ? "metric-result pass"
                      : "metric-result fail"
                  }
                >
                  {
                    evaluation.report_available
                      ? "READY"
                      : "CHECK"
                  }
                </span>

              </div>


              <div className="evaluation-last-run">

                <span>
                  Last evaluated
                </span>

                <strong>
                  {
                    evaluationEvaluatedAt
                      ? evaluationEvaluatedAt.toLocaleString()
                      : "Unknown"
                  }
                </strong>

              </div>


              <details className="evaluation-details">

                <summary>
                  View raw evaluation output
                </summary>

                <pre>
                  {
                    evaluation.output ||
                    "No raw output returned."
                  }
                </pre>

              </details>

            </>

          )}


        {evaluation?.status === "error" && (

          <div className="upload-result error">
            {evaluation.error}
          </div>

        )}

      </section>


      {/* ==================================================
          ASK
      ================================================== */}

      <section className="card">

        <div className="section-title">

          <div>

            <h2>
              Ask
            </h2>

            <p>
              Ask a question about your
              indexed knowledge base.
            </p>

          </div>

        </div>


        <textarea
          value={q}
          onChange={(event) =>
            setQ(event.target.value)
          }
          onKeyDown={handleKeyDown}
          placeholder="Example: How often is Pond 7 checked?"
          disabled={loading}
        />


        <div className="ask-row">

          <span className="hint">
            Enter to ask · Shift + Enter
            for a new line
          </span>


          <button
            onClick={ask}
            disabled={
              loading ||
              !q.trim()
            }
          >
            {
              loading
                ? "Retrieving..."
                : "Ask"
            }
          </button>

        </div>

      </section>


      {/* ==================================================
          ANSWER
      ================================================== */}

      {data && (

        <section className="card answer-card">

          <div className="answer-header">

            <h2>
              Answer
            </h2>


            {data.confidence && (

              <span
                className={
                  "confidence " +
                  data.confidence
                }
              >
                {data.confidence}
                {" confidence"}
              </span>

            )}

          </div>


          <div className="answer">
            {data.answer}
          </div>


          {/* =================================================
              RAG DIAGNOSTICS
          ================================================= */}

          {diagnostics && (

            <>

              <h3>
                RAG Diagnostics
              </h3>


              <div className="diagnostics-grid">

                <div>
                  <span>Retrieved</span>

                  <strong>
                    {diagnostics.retrieved_chunks}
                  </strong>
                </div>


                <div>
                  <span>Citations</span>

                  <strong>
                    {diagnostics.cited_sources}
                  </strong>
                </div>


                <div>
                  <span>Retrieval</span>

                  <strong>
                    {diagnostics.retrieval_ms} ms
                  </strong>
                </div>


                <div>
                  <span>Generation</span>

                  <strong>
                    {diagnostics.generation_ms} ms
                  </strong>
                </div>


                <div>
                  <span>Total</span>

                  <strong>
                    {diagnostics.total_ms} ms
                  </strong>
                </div>


                <div>
                  <span>Best Score</span>

                  <strong>
                    {
                      diagnostics.best_retrieval_score !==
                      null &&
                      diagnostics.best_retrieval_score !==
                      undefined

                        ? Number(
                            diagnostics.best_retrieval_score
                          ).toFixed(3)

                        : "N/A"
                    }
                  </strong>
                </div>

              </div>


              <div className="evaluation-meta">

                <span>
                  Grounded:{" "}
                  {diagnostics.grounded
                    ? "Yes"
                    : "No"}
                </span>


                <span>
                  Abstained:{" "}
                  {diagnostics.abstained
                    ? "Yes"
                    : "No"}
                </span>

              </div>


              {/* ============================================
                  RETRIEVAL INTELLIGENCE
              ============================================ */}

              {diagnostics.retrieval_pipeline && (

                <>

                  <h3 className="pipeline-title">
                    Retrieval Intelligence
                  </h3>


                  <div className="pipeline-overview">

                    <div className="pipeline-stage">

                      <span>
                        Dense Search
                      </span>

                      <strong>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .dense
                            ?.count ?? 0
                        }
                      </strong>

                      <small>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .dense
                            ?.latency_ms ?? 0
                        }{" "}
                        ms
                      </small>

                    </div>


                    <div className="pipeline-arrow">
                      →
                    </div>


                    <div className="pipeline-stage">

                      <span>
                        Lexical Search
                      </span>

                      <strong>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .lexical
                            ?.count ?? 0
                        }
                      </strong>

                      <small>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .lexical
                            ?.latency_ms ?? 0
                        }{" "}
                        ms
                      </small>

                    </div>


                    <div className="pipeline-arrow">
                      →
                    </div>


                    <div className="pipeline-stage">

                      <span>
                        RRF Fusion
                      </span>

                      <strong>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .rrf
                            ?.count ?? 0
                        }
                      </strong>

                      <small>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .rrf
                            ?.latency_ms ?? 0
                        }{" "}
                        ms
                      </small>

                    </div>


                    <div className="pipeline-arrow">
                      →
                    </div>


                    <div className="pipeline-stage">

                      <span>
                        Cross-Encoder
                      </span>

                      <strong>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .rerank
                            ?.returned_count ?? 0
                        }
                      </strong>

                      <small>
                        {
                          diagnostics
                            .retrieval_pipeline
                            .rerank
                            ?.latency_ms ?? 0
                        }{" "}
                        ms
                      </small>

                    </div>

                  </div>


                  <div className="ranking-table-wrap">

                    <table className="ranking-table">

                      <thead>

                        <tr>

                          <th>Final</th>
                          <th>Source</th>
                          <th>Dense</th>
                          <th>Lexical</th>
                          <th>RRF</th>
                          <th>Reranker</th>

                        </tr>

                      </thead>


                      <tbody>

                        {(diagnostics
                          .retrieval_pipeline
                          .stages || []
                        ).map(
                          (stage) => (

                            <tr
                              key={
                                stage.chunk_id
                              }
                            >

                              <td>

                                <span className="rank-badge">
                                  S
                                  {stage.final_rank}
                                </span>

                              </td>


                              <td>

                                <strong>
                                  {stage.source}
                                </strong>


                                {stage.page && (

                                  <span className="table-page">
                                    page{" "}
                                    {stage.page}
                                  </span>

                                )}

                              </td>


                              <td>
                                {
                                  stage.dense_rank
                                    ? `#${stage.dense_rank}`
                                    : "—"
                                }
                              </td>


                              <td>
                                {
                                  stage.lexical_rank
                                    ? `#${stage.lexical_rank}`
                                    : "—"
                                }
                              </td>


                              <td>
                                {
                                  stage.rrf_rank
                                    ? `#${stage.rrf_rank}`
                                    : "—"
                                }
                              </td>


                              <td>

                                <strong>
                                  {
                                    hasValue(
                                      stage.rerank_score
                                    )
                                      ? Number(
                                          stage.rerank_score
                                        ).toFixed(3)
                                      : "N/A"
                                  }
                                </strong>

                              </td>

                            </tr>

                          )
                        )}

                      </tbody>

                    </table>

                  </div>

                </>

              )}

            </>

          )}


          {/* =================================================
              SOURCES
          ================================================= */}

          <h3>
            Sources
          </h3>


          {data.citations?.length > 0 ? (

            <div className="sources">

              {data.citations.map(
                (source) => (

                  <div
                    className="source"
                    key={source.id}
                  >

                    <div>

                      <strong>
                        [{source.id}]{" "}
                        {source.source}
                      </strong>


                      {source.page && (

                        <span className="page">
                          · page{" "}
                          {source.page}
                        </span>

                      )}

                    </div>


                    <span className="score">

                      {
                        hasValue(
                          source.score
                        )
                          ? Number(
                              source.score
                            ).toFixed(3)
                          : "N/A"
                      }

                    </span>

                  </div>

                )
              )}

            </div>

          ) : (

            <p className="no-sources">
              No supporting sources found.
            </p>

          )}


          {/* =================================================
              EVIDENCE
          ================================================= */}

          {data.retrieved?.length > 0 && (

            <details className="evidence-inspector">

              <summary>
                Inspect retrieved evidence (
                {data.retrieved.length}
                )
              </summary>


              <div className="evidence-list">

                {data.retrieved.map(
                  (
                    item,
                    index
                  ) => (

                    <div
                      className="evidence-item"
                      key={
                        item.source +
                        "-" +
                        index
                      }
                    >

                      <div className="evidence-header">

                        <div>

                          <strong>
                            [S
                            {index + 1}
                            ]{" "}
                            {item.source}
                          </strong>


                          {item.page && (

                            <span className="page">
                              · page{" "}
                              {item.page}
                            </span>

                          )}

                        </div>


                        <span className="score">

                          {
                            hasValue(
                              item.score
                            )
                              ? Number(
                                  item.score
                                ).toFixed(3)
                              : "N/A"
                          }

                        </span>

                      </div>


                      <p>
                        {item.preview}
                      </p>

                    </div>

                  )
                )}

              </div>

            </details>

          )}

        </section>

      )}


      {/* ==================================================
          QUERY HISTORY
      ================================================== */}

      <section className="card history-card">

        <div className="section-title">

          <div>

            <h2>
              Query History
            </h2>

            <p>
              Persistent audit history with
              citations and retrieved evidence.
            </p>

          </div>


          <div className="history-actions">

            <button
              className="secondary-button"
              onClick={() => {
                loadHistory();
                loadAnalytics();
              }}
              disabled={historyLoading}
            >
              {
                historyLoading
                  ? "Refreshing..."
                  : "Refresh"
              }
            </button>


            <button
              className="danger-button"
              onClick={clearHistory}
              disabled={
                historyLoading ||
                history.length === 0
              }
            >
              Clear History
            </button>

          </div>

        </div>


        {historyLoading &&
          history.length === 0 && (

            <p className="muted">
              Loading query history...
            </p>

          )}


        {!historyLoading &&
          history.length === 0 && (

            <div className="empty-state">
              No query history yet.
            </div>

          )}


        {history.length > 0 && (

          <div className="history-list">

            {history.map(
              (item) => (

                <details
                  className="history-item"
                  key={item.id}
                >

                  <summary className="history-summary">

                    <div className="history-summary-main">

                      <h3>
                        {item.question}
                      </h3>


                      <div className="history-meta">

                        <span
                          className={
                            "status-pill " +
                            (
                              item.confidence ===
                              "high"

                                ? "status-success"

                                : item.confidence ===
                                  "medium"

                                  ? "status-warning"

                                  : "status-neutral"
                            )
                          }
                        >
                          {item.confidence}
                        </span>


                        <span>
                          {
                            item.grounded
                              ? "Grounded"
                              : "Not grounded"
                          }
                        </span>


                        {item.abstained && (

                          <span>
                            Abstained
                          </span>

                        )}


                        <span>
                          {item.total_ms} ms
                        </span>

                      </div>

                    </div>


                    <span className="history-time">

                      {
                        item.created_at
                          ? new Date(
                              item.created_at
                            ).toLocaleString()
                          : "Unknown time"
                      }

                    </span>

                  </summary>


                  <div className="history-content">

                    <div className="history-answer-block">

                      <span className="history-label">
                        Answer
                      </span>

                      <p className="history-answer">
                        {item.answer}
                      </p>

                    </div>


                    <div className="history-diagnostics">

                      <span>
                        {item.total_ms} ms
                      </span>

                      <span>
                        {item.retrieved_chunks} chunks
                      </span>

                      <span>
                        {item.cited_sources} citation
                        {
                          item.cited_sources === 1
                            ? ""
                            : "s"
                        }
                      </span>

                      <span>
                        Retrieval{" "}
                        {item.retrieval_ms} ms
                      </span>

                      <span>
                        Generation{" "}
                        {item.generation_ms} ms
                      </span>

                    </div>


                    <div className="history-section">

                      <h4>
                        Citations
                      </h4>


                      {item.citations?.length > 0 ? (

                        <div className="sources">

                          {item.citations.map(
                            (citation) => (

                              <div
                                className="source"
                                key={citation.id}
                              >

                                <div>

                                  <strong>
                                    [
                                    {citation.id}
                                    ]{" "}
                                    {citation.source}
                                  </strong>


                                  {citation.page && (

                                    <span className="page">
                                      · page{" "}
                                      {citation.page}
                                    </span>

                                  )}

                                </div>


                                {citation.score !==
                                  undefined && (

                                  <span className="score">
                                    {
                                      hasValue(
                                        citation.score
                                      )
                                        ? Number(
                                            citation.score
                                          ).toFixed(3)
                                        : "N/A"
                                    }
                                  </span>

                                )}

                              </div>

                            )
                          )}

                        </div>

                      ) : (

                        <p className="muted">
                          No citations recorded.
                        </p>

                      )}

                    </div>


                    <div className="history-section">

                      <h4>
                        Retrieved Evidence
                      </h4>


                      {item.evidence?.length > 0 ? (

                        <div className="evidence-list">

                          {item.evidence.map(
                            (
                              evidence,
                              index
                            ) => (

                              <div
                                className="evidence-item"
                                key={
                                  item.id +
                                  "-" +
                                  index
                                }
                              >

                                <div className="evidence-header">

                                  <div>

                                    <strong>
                                      [S
                                      {index + 1}
                                      ]{" "}
                                      {evidence.source}
                                    </strong>


                                    {evidence.page && (

                                      <span className="page">
                                        · page{" "}
                                        {evidence.page}
                                      </span>

                                    )}

                                  </div>


                                  <span className="score">

                                    {
                                      hasValue(
                                        evidence.score
                                      )
                                        ? Number(
                                            evidence.score
                                          ).toFixed(3)
                                        : "N/A"
                                    }

                                  </span>

                                </div>


                                <p>
                                  {evidence.preview}
                                </p>

                              </div>

                            )
                          )}

                        </div>

                      ) : (

                        <p className="muted">
                          No retrieved evidence
                          recorded for this query.
                        </p>

                      )}

                    </div>

                  </div>

                </details>

              )
            )}

          </div>

        )}

      </section>

    </main>
  );
}


createRoot(
  document.getElementById("root")
).render(
  <App />
);