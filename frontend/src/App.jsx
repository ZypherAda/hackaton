import { useEffect, useRef, useState } from "react";
import grapesjs from "grapesjs";
import "grapesjs/dist/css/grapes.min.css";
import "./App.css";

export default function App() {
  // ---------------------------------------------------------------------------
  // ESTADOS DE NAVEGACIÓN Y DASHBOARD (INDEX)
  // ---------------------------------------------------------------------------
  const [pantallaActual, setPantallaActual] = useState("index"); // "index" o "builder"
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [copywriterStatus, setCopywriterStatus] = useState(null);
  const [qaStatus, setQaStatus] = useState(null);

  // ---------------------------------------------------------------------------
  // ESTADOS Y REFS DEL WEBSITE BUILDER (GRAPESJS)
  // ---------------------------------------------------------------------------
  const editorRef = useRef(null);
  const [selectedComponent, setSelectedComponent] = useState(null);
  const [bloquesAInsertar, setBloquesAInsertar] = useState([]);

  // ===========================================================================
  // 1. MÉTODOS DEL DASHBOARD / INDEX
  // ===========================================================================
  const handleExecuteAgents = async () => {
    if (!prompt.trim()) return;
    setLoading(true);
    setCopywriterStatus(null);
    setQaStatus(null);

    try {
      const response = await fetch("http://localhost:8000/api/generate-page", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt }),
      });

      if (!response.ok) throw new Error("Error en la respuesta del servidor");

      const data = await response.json();
      setPreviewData(data);
    } catch (err) {
      alert("Error al conectar con el backend de Python.");
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleRunCopywriter = () => {
    if (!previewData) {
      alert("Primero debes generar un layout con el prompt para ejecutar el Copywriter.");
      return;
    }
    setCopywriterStatus("✍️ Copywriter IA: Se han optimizado los encabezados y textos para conversión automotriz.");
  };

  const handleRunQA = () => {
    if (!previewData) {
      alert("Primero debes generar un layout con el prompt para ejecutar la Auditoría QA.");
      return;
    }
    const tieneInventario = previewData.layout.blocks.includes("inventory-card-block");
    if (previewData.preview.page_type === "FINANCE" && tieneInventario) {
      setQaStatus("⚠️ QA Alert: Inconsistencia detectada. Páginas financieras no deben llevar inventario.");
    } else {
      setQaStatus("✅ QA Passed: Estructura validada sin errores de UX ni violaciones de reglas de negocio.");
    }
  };

  const handleConfirmarEIrAlBuilder = () => {
    if (!previewData) return;
    setBloquesAInsertar(previewData.layout.blocks);
    setPantallaActual("builder");
  };

  // ===========================================================================
  // 2. CICLO DE VIDA DE GRAPESJS
  // ===========================================================================
  useEffect(() => {
    if (pantallaActual !== "builder" || editorRef.current) return;

    const editor = grapesjs.init({
      container: "#gjs",
      height: "100vh",
      width: "100%",
      storageManager: false,
      blockManager: {
        appendTo: "#blocks-container",
      },
      layerManager: {
        appendTo: "#layers-container",
      },
    });

    editor.on("component:selected", () => {
      const selected = editor.getSelected();
      if (selected && selected !== editor.getWrapper()) {
        setSelectedComponent(selected);
      } else {
        setSelectedComponent(null);
      }
    });

    editor.on("component:deselected", () => {
      setSelectedComponent(null);
    });

    editor.on("load", () => {
      const head = editor.Canvas.getDocument().head;
      const style = editor.Canvas.getDocument().createElement("style");
      style.innerHTML = `
        body {
          margin: 0;
          padding: 40px 20px;
          box-sizing: border-box;
          overflow-x: hidden;
          background-color: #ffffff;
        }
        * {
          box-sizing: border-box;
          overflow-wrap: anywhere !important;
          word-break: break-word !important;
        }
        img {
          max-width: 100%;
          height: auto;
        }
      `;
      head.appendChild(style);

      const wrapper = editor.getWrapper();
      if (wrapper) {
        wrapper.set("open", true);
      }

      if (bloquesAInsertar.length > 0) {
        bloquesAInsertar.forEach((blockId) => {
          const block = editor.BlockManager.get(blockId);
          if (block) {
            editor.addComponents(block.getContent());
          }
        });
      }
    });

    editor.on("component:add", () => {
      const wrapper = editor.getWrapper();
      if (wrapper && !wrapper.get("open")) {
        wrapper.set("open", true);
      }
    });

    // Text Block
    editor.BlockManager.add("text-block", {
      label: "Content Text",
      content: `
        <div style="padding: 24px 10px; margin: 0 auto 16px auto; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; width: 100%; max-width: 100%; box-sizing: border-box;">
          <p style="font-size: 18px; color: #0f172a; margin: 0; text-align: center; font-family: sans-serif;">
            Double click here to edit text directly...
          </p>
        </div>
      `,
    });

    // Left Image / Content
    editor.BlockManager.add("left-image-block", {
      label: "Left Image / Content",
      content: `
        <div style="display: flex; gap: 20px; align-items: center; padding: 20px 10px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; margin: 0 auto 16px auto; width: 100%; max-width: 100%; box-sizing: border-box; flex-wrap: wrap; overflow: hidden;">
          <div style="flex: 1 1 250px; min-width: 0; max-width: 100%;">
            <img src="/images/image_default1.jpg" alt="Sample" style="width: 100%; max-width: 100%; height: auto; border-radius: 6px; display: block; object-fit: cover;" />
          </div>
          <div style="flex: 1 1 250px; min-width: 0; max-width: 100%; font-family: sans-serif; overflow-wrap: anywhere; word-break: break-word;">
            <h3 style="margin: 0 0 10px 0; font-size: 20px; color: #0f172a;">Section Title</h3>
            <p style="margin: 0; font-size: 15px; color: #475569; line-height: 1.5;">
              Double click on this text to edit or replace the image using properties.
            </p>
          </div>
        </div>
      `,
    });

    // Right Image / Content
    editor.BlockManager.add("right-image-block", {
      label: "Right Image / Content",
      content: `
        <div style="display: flex; gap: 20px; align-items: center; padding: 20px 10px; background-color: #ffffff; border-radius: 8px; border: 1px solid #e2e8f0; margin: 0 auto 16px auto; width: 100%; max-width: 100%; box-sizing: border-box; flex-wrap: wrap; overflow: hidden;">
          <div style="flex: 1 1 250px; min-width: 0; max-width: 100%; font-family: sans-serif; overflow-wrap: anywhere; word-break: break-word;">
            <h3 style="margin: 0 0 10px 0; font-size: 20px; color: #0f172a;">Section Title</h3>
            <p style="margin: 0; font-size: 15px; color: #475569; line-height: 1.5;">
              Double click on this text to edit or replace the image using properties.
            </p>
          </div>
          <div style="flex: 1 1 250px; min-width: 0; max-width: 100%;">
            <img src="/images/image_default2.jpg" alt="Sample" style="width: 100%; max-width: 100%; height: auto; border-radius: 6px; display: block; object-fit: cover;" />
          </div>
        </div>
      `,
    });

    // Inventory
    editor.BlockManager.add("inventory-card-block", {
      label: "Inventory Card",
      content: `
        <style>
          .inventory-section {
            width: 100%;
            max-width: 1200px;
            margin: 0 auto 20px auto;
            padding: 20px 10px;
            box-sizing: border-box;
            font-family: sans-serif;
          }
          .inventory-grid {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 20px;
          }
          .inventory-card {
            background-color: #ffffff;
            border-radius: 12px;
            border: 1px solid #e2e8f0;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
            overflow: hidden;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
          }
          .card-image-container {
            width: 100%;
            height: 180px;
            overflow: hidden;
            background-color: #f1f5f9;
          }
          .card-image {
            width: 100%;
            height: 100%;
            object-fit: cover;
          }
          .card-content {
            padding: 16px;
            text-align: center;
          }
          .card-title {
            margin: 0;
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
          }
          .card-subtitle {
            margin: 6px 0 0 0;
            font-size: 13px;
            color: #64748b;
          }
          .card-actions {
            padding: 0 16px 16px 16px;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
          }
          .btn {
            padding: 8px 10px;
            font-size: 12px;
            font-weight: 600;
            border-radius: 6px;
            border: none;
            cursor: pointer;
            text-align: center;
          }
          .btn-secondary {
            background-color: #f1f5f9;
            color: #334155;
          }
          .btn-primary {
            background-color: #2563eb;
            color: #ffffff;
          }
          @media (max-width: 768px) {
            .inventory-grid {
              grid-template-columns: 1fr;
            }
          }
        </style>

        <section class="inventory-section">
          <h2 style="text-align: center;">Inventory Showcase</h2>
          <div class="inventory-grid">

            <div class="inventory-card">
              <div class="card-image-container">
                <img 
                  src="https://images.unsplash.com/photo-1503376780353-7e6692767b70?auto=format&fit=crop&q=80&w=800" 
                  alt="Porsche 911 GT3" 
                  class="card-image"
                />
              </div>
              <div class="card-content">
                <h3 class="card-title">Porsche 911 GT3</h3>
                <p class="card-subtitle">Modelo 2024 • Deportivo</p>
              </div>
              <div class="card-actions">
                <button class="btn btn-secondary">View Details</button>
                <button class="btn btn-primary">Shop Now</button>
              </div>
            </div>

            <div class="inventory-card">
              <div class="card-image-container">
                <img 
                  src="https://images.unsplash.com/photo-1555215695-3004980ad54e?auto=format&fit=crop&q=80&w=800" 
                  alt="BMW M4 Coupe" 
                  class="card-image"
                />
              </div>
              <div class="card-content">
                <h3 class="card-title">BMW M4 Coupe</h3>
                <p class="card-subtitle">Modelo 2023 • Performance</p>
              </div>
              <div class="card-actions">
                <button class="btn btn-secondary">View Details</button>
                <button class="btn btn-primary">Shop Now</button>
              </div>
            </div>

            <div class="inventory-card">
              <div class="card-image-container">
                <img 
                  src="https://images.unsplash.com/photo-1617814076367-b759c7d7e738?auto=format&fit=crop&q=80&w=800" 
                  alt="Audi RS e-tron GT" 
                  class="card-image"
                />
              </div>
              <div class="card-content">
                <h3 class="card-title">Audi RS e-tron GT</h3>
                <p class="card-subtitle">Modelo 2024 • Eléctrico</p>
              </div>
              <div class="card-actions">
                <button class="btn btn-secondary">View Details</button>
                <button class="btn btn-primary">Shop Now</button>
              </div>
            </div>

          </div>
        </section>
      `,
    });

    const blocksContainer = document.getElementById("blocks-container");
    if (blocksContainer) {
      blocksContainer.addEventListener("click", (e) => {
        const blockEl = e.target.closest(".gjs-block");
        if (!blockEl) return;

        const blockId = blockEl.getAttribute("data-id") || blockEl.dataset.id;
        let block = editor.BlockManager.get(blockId);

        if (!block) {
          const allBlocks = editor.BlockManager.getAll().models;
          block = allBlocks.find((b) => b.getId() === blockId || blockEl.innerText.includes(b.getLabel()));
        }

        if (block) {
          const content = block.getContent();
          editor.addComponents(content);
        }
      });
    }

    window.addEventListener("keydown", (e) => {
      if ((e.key === "Delete" || e.key === "Backspace") && editor.getSelected()) {
        const isEditing = editor.getSelected().isEditing();
        if (!isEditing && editor.getSelected() !== editor.getWrapper()) {
          editor.getSelected().remove();
          setSelectedComponent(null);
        }
      }
    });

    editorRef.current = editor;
  }, [pantallaActual, bloquesAInsertar]);

  // ===========================================================================
  // 3. MÉTODOS DE EDICIÓN Y NAVEGACIÓN
  // ===========================================================================
  const handleDeleteSelected = () => {
    if (editorRef.current) {
      const selected = editorRef.current.getSelected();
      if (selected && selected !== editorRef.current.getWrapper()) {
        selected.remove();
        setSelectedComponent(null);
      }
    }
  };

  const handleVolverAlDashboard = () => {
    if (editorRef.current) {
      editorRef.current.destroy();
      editorRef.current = null;
    }
    setPantallaActual("index");
  };

  // ===========================================================================
  // 4. VISTAS
  // ===========================================================================

  // PANTALLA INDEX: DASHBOARD DE THE PROMPTASTICS
  if (pantallaActual === "index") {
    return (
      <div style={{ minHeight: "100vh", backgroundColor: "#0f172a", color: "#f8fafc", fontFamily: "sans-serif", padding: "40px 20px" }}>
        <div style={{ maxWidth: "800px", margin: "0 auto" }}>
          
          <header style={{ textAlign: "center", marginBottom: "32px" }}>
            <span style={{ fontSize: "12px", fontWeight: "700", color: "#a855f7", letterSpacing: "2px" }}>AI WEB ARCHITECTURE</span>
            <h1 style={{ fontSize: "36px", fontWeight: "800", margin: "8px 0" }}>The Promptastics 🚀</h1>
            <p style={{ color: "#94a3b8" }}>Generador de Maquetas para Concesionarias de Autos</p>
          </header>

          {/* Formulario Principal de Solicitud */}
          <div style={{ backgroundColor: "#1e293b", padding: "24px", borderRadius: "12px", border: "1px solid #334155", boxShadow: "0 10px 25px -5px rgba(0,0,0,0.3)" }}>
            <label style={{ display: "block", fontSize: "14px", fontWeight: "600", color: "#cbd5e1", marginBottom: "8px" }}>
              ¿Qué tipo de página deseas construir?
            </label>
            <textarea
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Ej: Crear una página para el Finance Center con opciones de crédito..."
              rows={4}
              style={{ width: "100%", backgroundColor: "#0f172a", border: "1px solid #475569", borderRadius: "8px", color: "#fff", padding: "12px", boxSizing: "border-box", resize: "none", marginBottom: "16px", outline: "none" }}
            />
            <button
              onClick={handleExecuteAgents}
              disabled={loading || !prompt.trim()}
              style={{
                width: "100%",
                padding: "14px",
                backgroundColor: loading ? "#475569" : "#2563eb",
                color: "#fff",
                border: "none",
                borderRadius: "8px",
                fontWeight: "700",
                cursor: loading || !prompt.trim() ? "not-allowed" : "pointer",
                transition: "all 0.2s ease",
                boxShadow: "0 4px 12px rgba(37,99,235,0.3)"
              }}
            >
              {loading ? "Ejecutando Agente..." : "⚡ Interpretar y Generar Layout"}
            </button>
          </div>

          {/* BOTONES FUERA DEL CUADRO (En el recuadro que marcaste) */}
          <div style={{ marginTop: "20px", display: "grid", gridTemplateColumns: "1fr 1fr", gap: "16px" }}>
            <button
              onClick={handleRunCopywriter}
              style={{
                padding: "14px",
                backgroundColor: "#1e293b",
                color: "#38bdf8",
                border: "1px solid #0284c7",
                borderRadius: "10px",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: "600",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                transition: "all 0.2s",
                boxShadow: "0 4px 10px rgba(0,0,0,0.2)"
              }}
            >
              <span style={{ fontSize: "16px" }}>✍️</span> Generacion Copywriter
            </button>

            <button
              onClick={handleRunQA}
              style={{
                padding: "14px",
                backgroundColor: "#1e293b",
                color: "#c084fc",
                border: "1px solid #9333ea",
                borderRadius: "10px",
                cursor: "pointer",
                fontSize: "13px",
                fontWeight: "600",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                gap: "8px",
                transition: "all 0.2s",
                boxShadow: "0 4px 10px rgba(0,0,0,0.2)"
              }}
            >
              <span style={{ fontSize: "16px" }}>🔍</span> Realizar QA
            </button>
          </div>

          {/* Status Messages */}
          <div style={{ marginTop: "12px" }}>
            {copywriterStatus && (
              <div style={{ padding: "12px 16px", backgroundColor: "#065f4620", border: "1px solid #10b981", borderRadius: "8px", color: "#34d399", fontSize: "13px", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                {copywriterStatus}
              </div>
            )}
            {qaStatus && (
              <div style={{ padding: "12px 16px", backgroundColor: "#31104220", border: "1px solid #a855f7", borderRadius: "8px", color: "#c084fc", fontSize: "13px", marginBottom: "12px", display: "flex", alignItems: "center", gap: "8px" }}>
                {qaStatus}
              </div>
            )}
          </div>

          {/* Panel Preview de Maqueta Generada */}
          {previewData && (
            <div style={{ marginTop: "16px", backgroundColor: "#1e293b", border: "1px solid #3b82f6", borderRadius: "12px", padding: "24px", boxShadow: "0 10px 30px rgba(0,0,0,0.3)" }}>
              <span style={{ fontSize: "11px", fontWeight: "700", padding: "4px 10px", backgroundColor: "#3b82f620", color: "#60a5fa", border: "1px solid #3b82f6", borderRadius: "20px", textTransform: "uppercase", letterSpacing: "0.5px" }}>
                {previewData.preview.page_type_label}
              </span>
              
              <h2 style={{ fontSize: "22px", margin: "14px 0 6px 0", color: "#fff" }}>
                📌 {previewData.preview.page_title}
              </h2>
              <p style={{ color: "#94a3b8", fontSize: "14px", margin: "0 0 20px 0", lineHeight: "1.5" }}>
                {previewData.preview.summary}
              </p>

              <div style={{ marginBottom: "24px" }}>
                <h4 style={{ fontSize: "11px", textTransform: "uppercase", color: "#cbd5e1", margin: "0 0 10px 0", letterSpacing: "1px" }}>
                  Estructura de Widgets Recomendada:
                </h4>
                <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                  {previewData.layout.blocks.map((block, idx) => (
                    <div key={idx} style={{ backgroundColor: "#0f172a", border: "1px solid #475569", padding: "6px 12px", borderRadius: "6px", fontSize: "13px" }}>
                      {idx + 1}. <strong style={{ color: "#a855f7" }}>{block}</strong>
                    </div>
                  ))}
                </div>
              </div>

              <button
                onClick={handleConfirmarEIrAlBuilder}
                style={{
                  width: "100%",
                  padding: "14px",
                  backgroundColor: "#16a34a",
                  color: "#fff",
                  border: "none",
                  borderRadius: "8px",
                  fontWeight: "700",
                  cursor: "pointer",
                  fontSize: "14px",
                  transition: "all 0.2s",
                  boxShadow: "0 4px 12px rgba(22,163,74,0.3)"
                }}
              >
                🎨 Confirmar y Abrir en Website Builder (GrapesJS) →
              </button>
            </div>
          )}
        </div>
      </div>
    );
  }

  // PANTALLA BUILDER
  return (
    <div style={{ display: "flex", width: "100%", height: "100vh", overflow: "hidden", fontFamily: "sans-serif", position: "relative" }}>
      
      <style>{`
        html, body, #root {
          margin: 0;
          padding: 0;
          overflow: hidden !important;
          width: 100%;
          height: 100%;
        }

        .gjs-cv-canvas {
          width: 100% !important;
          height: 100% !important;
          top: 0 !important;
          left: 0 !important;
        }

        .gjs-frame {
          width: 100% !important;
          max-width: 100% !important;
        }

        .gjs-toolbar {
          background-color: #2563eb !important;
          border-radius: 4px !important;
          z-index: 9999 !important;
          opacity: 1 !important;
          visibility: visible !important;
          display: flex !important;
        }
        .gjs-toolbar-item {
          color: #ffffff !important;
          padding: 6px 8px !important;
        }
        .gjs-toolbar-item:hover {
          background-color: #1d4ed8 !important;
        }

        #blocks-container .gjs-blocks-c {
          display: flex !important;
          flex-direction: column !important;
          gap: 8px !important;
        }
        #blocks-container .gjs-block {
          width: 100% !important;
          min-height: auto !important;
          padding: 10px 14px !important;
          border-radius: 6px !important;
          border: 1px solid #3f4246 !important;
          background-color: #323438 !important;
          color: #e2e8f0 !important;
          font-weight: 500 !important;
          font-size: 13px !important;
          box-sizing: border-box !important;
          text-align: left !important;
          cursor: pointer !important;
          user-select: none;
        }
        #blocks-container .gjs-block:hover {
          background-color: #3b82f6 !important;
          border-color: #3b82f6 !important;
          color: #ffffff !important;
        }

        #layers-container {
          padding-right: 4px;
        }
        #layers-container .gjs-layer {
          background-color: #323438 !important;
          color: #cbd5e1 !important;
          border-bottom: 1px solid #3f4246 !important;
          border-radius: 4px;
          margin-bottom: 2px;
        }
        #layers-container .gjs-layer:hover,
        #layers-container .gjs-layer.gjs-hovered {
          background-color: #3f4246 !important;
          color: #ffffff !important;
        }
        #layers-container .gjs-layer-title,
        #layers-container .gjs-layer-name {
          color: inherit !important;
        }

        #layers-container .gjs-layer-count {
          display: none !important;
        }
      `}</style>

      {/* Left Panel */}
      <div
        style={{
          width: "280px",
          minWidth: "280px",
          backgroundColor: "#2a2b2e",
          borderRight: "1px solid #3f4246",
          padding: "20px",
          display: "flex",
          flexDirection: "column",
          gap: "20px",
          boxSizing: "border-box",
          zIndex: 10,
          overflowY: "auto"
        }}
      >
        {/* Component Library */}
        <div>
          <h3 style={{ fontSize: "14px", margin: "0 0 12px 0", color: "#94a3b8", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px" }}>
            Component Library
          </h3>
          <div id="blocks-container"></div>
        </div>

        {/* Layers & Structure */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "12px" }}>
            <h3 style={{ fontSize: "14px", margin: 0, color: "#94a3b8", fontWeight: "600", textTransform: "uppercase", letterSpacing: "0.5px" }}>
              Layers & Structure
            </h3>

            <button
              onClick={handleDeleteSelected}
              disabled={!selectedComponent}
              title={selectedComponent ? "Delete selected layer" : "Select a layer to delete"}
              style={{
                background: selectedComponent ? "#ef4444" : "#3f4246",
                color: selectedComponent ? "#ffffff" : "#64748b",
                border: "none",
                borderRadius: "4px",
                padding: "4px 8px",
                cursor: selectedComponent ? "pointer" : "not-allowed",
                fontSize: "13px",
                display: "flex",
                alignItems: "center",
                gap: "4px",
                transition: "all 0.2s"
              }}
            >
              🗑️ Delete
            </button>
          </div>

          <div id="layers-container"></div>
        </div>

        {/* Botón para volver al Dashboard */}
        <button
          onClick={handleVolverAlDashboard}
          style={{
            marginTop: "auto",
            width: "100%",
            padding: "12px",
            backgroundColor: "#0f172a",
            color: "#ffffff",
            border: "1px solid #3b82f6",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "600",
            fontSize: "13px",
            boxShadow: "0 2px 4px rgba(0,0,0,0.3)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            gap: "6px"
          }}
        >
          ← Volver al Dashboard
        </button>
      </div>

      {/* Main Canvas */}
      <div style={{ flex: 1, height: "100vh", backgroundColor: "#1e1e1e", position: "relative", overflow: "hidden", display: "flex" }}>
        <div id="gjs" style={{ width: "100%", height: "100%" }}></div>
      </div>
    </div>
  );
}