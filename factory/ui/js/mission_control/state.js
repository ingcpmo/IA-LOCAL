/* W5 — estado de sesión compartido de Mission Control.
   La API key vive SOLO en memoria (sin localStorage), igual que en el
   monolito original. Los módulos leen/escriben via el objeto `state`
   (nunca re-exportar los valores sueltos: perderían la mutabilidad). */

export const API_BASE = "";

export const state = {
  apiKey: "",
  connected: false,
  selectedMissionId: null,  // W4/TAREA3: misión abierta en el detail panel; null = "Selecciona una misión"
};

export function headers(){ return {'Content-Type':'application/json','x-api-key':state.apiKey}; }
