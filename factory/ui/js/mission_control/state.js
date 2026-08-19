/* W5 — estado de sesión compartido de Mission Control.
   La API key vive SOLO en memoria (sin localStorage), igual que en el
   monolito original. Los módulos leen/escriben via el objeto `state`
   (nunca re-exportar los valores sueltos: perderían la mutabilidad).

   identityKey (Paquete 2, hallazgo M, 2026-08-19): segunda credencial,
   distinta de apiKey -- resuelve la identidad humana autenticada
   (X-Identity-Key) que los endpoints de gobernanza exigen desde
   require_identity(). Mismo patron de sesion en memoria, nunca
   localStorage. Sin ella, cualquier POST que registre una decision
   (aprobar/rechazar/confirmar/firmar) devuelve 401 -- ya no basta con
   la API key compartida. */

export const API_BASE = "";

export const state = {
  apiKey: "",
  identityKey: "",
  connected: false,
  selectedMissionId: null,  // W4/TAREA3: misión abierta en el detail panel; null = "Selecciona una misión"
};

export function headers(){
  return {
    'Content-Type': 'application/json',
    'x-api-key': state.apiKey,
    'X-Identity-Key': state.identityKey,
  };
}
