import "../host/bootstrap-standalone-react";
import "../host/bootstrap-standalone";
import "../styles.css";
import "../components/pipeline-viewer/styles.css";
import "@xyflow/react/dist/style.css";
import { createRoot } from "react-dom/client";
import { PdeExtensionApp } from "../app/App";

const root = document.getElementById("root");
if (!root) throw new Error("Missing #root element for standalone UI");

createRoot(root).render(<PdeExtensionApp />);
