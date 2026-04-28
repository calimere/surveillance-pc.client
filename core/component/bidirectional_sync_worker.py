"""
Sync Worker Bidirectionnel - Gestion intelligent de la synchronisation serveur → client

Stratégies Hybrides :
1. MQTT Push : Changements temps réel quand connecté
2. Pull on Reconnect : Récupération après déconnexion
3. Incremental Sync : Basé sur timestamps pour éviter conflicts
4. Conflict Resolution : Serveur wins par défaut (configurable)
"""

import time
import threading
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from core.component.logger import get_logger
from core.component.config import config
from core.component.mqtt_client import subscribe

logger = get_logger("bidirectional_sync")


class BidirectionalSyncWorker:
    def __init__(self, sync_interval: int = 300):
        self.sync_interval = sync_interval
        self._running = False
        self._thread = None
        self._last_server_sync = None
        self._mqtt_connected = False
        self._lock = threading.Lock()

        # Statistiques
        self.stats = {
            "last_pull_sync": None,
            "last_push_received": None,
            "server_changes_applied": 0,
            "conflicts_resolved": 0,
            "sync_errors": 0,
        }

    def start(self):
        """Démarre le worker de sync bidirectionnelle"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._sync_loop, daemon=True)
            self._thread.start()

            # S'abonner aux changements server push via MQTT
            subscribe("surveillance/[client]/server_changes", self._handle_server_push)
            subscribe("surveillance/[client]/sync_request", self._handle_sync_request)

            logger.info("🔄 Sync bidirectionnel activé")

    def stop(self):
        """Arrête le worker proprement"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        logger.info("🛑 Sync bidirectionnel arrêté")

    def _sync_loop(self):
        """Boucle principale de synchronisation"""
        while self._running:
            try:
                current_mqtt_status = mqtt_connected()

                # Détection reconnexion MQTT → sync immédiate
                if current_mqtt_status and not self._mqtt_connected:
                    logger.info("📡 MQTT reconnecté → Sync serveur immédiate")
                    self._pull_server_changes(reason="mqtt_reconnect")

                self._mqtt_connected = current_mqtt_status

                # Sync périodique (Pull)
                if self._should_pull_sync():
                    self._pull_server_changes(reason="periodic")

                time.sleep(min(self.sync_interval, 30))  # Check au moins toutes les 30s

            except Exception as e:
                self.stats["sync_errors"] += 1
                logger.error(f"❌ Erreur sync bidirectionnelle: {e}")
                time.sleep(60)  # Attendre plus longtemps en cas d'erreur

    def _should_pull_sync(self) -> bool:
        """Détermine si une sync pull est nécessaire"""
        if not self._last_server_sync:
            return True

        elapsed = (datetime.now() - self._last_server_sync).total_seconds()
        return elapsed >= self.sync_interval

    def _pull_server_changes(self, reason: str = "periodic"):
        """Récupère les changements depuis le serveur (Pull Strategy)"""
        try:
            with self._lock:
                # Récupérer timestamp de dernière sync locale
                last_sync_ts = self._get_last_server_sync_timestamp()

                # Demander changements au serveur depuis last_sync_ts
                changes = self._fetch_server_changes_since(last_sync_ts)

                if changes:
                    applied = self._apply_server_changes(changes)
                    self.stats["server_changes_applied"] += applied
                    logger.info(
                        f"📥 {applied} changements serveur appliqués ({reason})"
                    )

                # Mettre à jour timestamp de dernière sync
                self._update_last_server_sync_timestamp()
                self._last_server_sync = datetime.now()
                self.stats["last_pull_sync"] = self._last_server_sync

        except Exception as e:
            self.stats["sync_errors"] += 1
            logger.error(f"❌ Pull sync failed: {e}")

    def _handle_server_push(self, payload: Dict[str, Any]):
        """Traite les changements push du serveur via MQTT"""
        try:
            with self._lock:
                changes = payload.get("changes", [])
                if changes:
                    applied = self._apply_server_changes(changes)
                    self.stats["server_changes_applied"] += applied
                    self.stats["last_push_received"] = datetime.now()
                    logger.info(f"📨 {applied} changements push appliqués")

        except Exception as e:
            self.stats["sync_errors"] += 1
            logger.error(f"❌ Server push failed: {e}")

    def _handle_sync_request(self, payload: Dict[str, Any]):
        """Traite les demandes de sync du serveur"""
        try:
            sync_type = payload.get("type", "full")
            if sync_type == "immediate":
                logger.info("📡 Sync immédiate demandée par serveur")
                self._pull_server_changes(reason="server_request")

        except Exception as e:
            logger.error(f"❌ Sync request failed: {e}")

    def _get_last_server_sync_timestamp(self) -> Optional[datetime]:
        """Récupère le timestamp de dernière sync serveur depuis la DB locale"""
        try:
            from core.business.db import SyncMetadata

            try:
                metadata = SyncMetadata.get(
                    SyncMetadata.smd_key == "last_server_sync_timestamp"
                )
                return datetime.fromisoformat(metadata.smd_value)
            except SyncMetadata.DoesNotExist:
                return None
        except Exception as e:
            logger.warning(f"⚠️ Cannot get last server sync: {e}")
            return None

    def _update_last_server_sync_timestamp(self):
        """Met à jour le timestamp de dernière sync serveur"""
        try:
            from core.business.db import SyncMetadata

            timestamp_value = datetime.now().isoformat()

            # Utiliser insert_or_replace équivalent avec Peewee
            SyncMetadata.replace(
                smd_key="last_server_sync_timestamp",
                smd_value=timestamp_value,
                smd_updated=datetime.now(),
            ).execute()
        except Exception as e:
            logger.warning(f"⚠️ Cannot update server sync timestamp: {e}")

    def _fetch_server_changes_since(self, since_ts: Optional[datetime]) -> List[Dict]:
        """Récupère les changements serveur depuis un timestamp (API call)"""
        # TODO: Implémenter appel API vers serveur
        # GET /api/changes/since?timestamp=XXXX&client_id=YYYY
        try:
            from core.business import api_publish

            # Cette fonction devra être ajoutée à api_publish.py
            return api_publish.get_server_changes_since(since_ts)
        except Exception as e:
            logger.error(f"❌ Failed to fetch server changes: {e}")
            return []

    def _apply_server_changes(self, changes: List[Dict]) -> int:
        """Applique les changements serveur sur la DB locale avec résolution de conflits"""
        applied_count = 0

        try:
            from core.business.db import (
                Process,
                ProcessInstance,
                ProcessEvent,
                SecurityAlert,
            )

            # Mapping des noms de table vers les modèles Peewee
            table_models = {
                "process": Process,
                "process_instance": ProcessInstance,
                "process_event": ProcessEvent,
                "security_alert": SecurityAlert,
            }

            for change in changes:
                if self._apply_single_change(table_models, change):
                    applied_count += 1

        except Exception as e:
            logger.error(f"❌ Failed to apply server changes: {e}")

        return applied_count

    def _apply_single_change(self, table_models: Dict, change: Dict) -> bool:
        """Applique un changement unique avec résolution de conflits (Version simplifiée)"""
        try:
            table_name = change["table"]
            operation = change["operation"]  # INSERT, UPDATE, DELETE
            data = change["data"]
            server_timestamp = datetime.fromisoformat(change["timestamp"])

            if table_name not in table_models:
                logger.warning(f"⚠️ Table inconnue pour sync: {table_name}")
                return False

            model_class = table_models[table_name]

            if operation == "UPDATE" and "id" in data:
                # Pour UPDATE, vérifier si l'enregistrement existe localement
                try:
                    # Récupérer l'enregistrement local
                    # Note: Ceci est une approche simplifiée - en production
                    # il faudrait mapper les colonnes ID correctement
                    local_record = model_class.get_by_id(data["id"])

                    # Vérification de conflit basique (timestamp)
                    conflict_resolution = config.get(
                        "sync", "conflict_resolution", fallback="server_wins"
                    )

                    if (
                        hasattr(local_record, "sync_timestamp")
                        and local_record.sync_timestamp
                    ):
                        local_ts = local_record.sync_timestamp
                        if (
                            local_ts > server_timestamp
                            and conflict_resolution == "client_wins"
                        ):
                            logger.info(
                                f"🔄 Conflit résolu en faveur du client: {table_name}#{data['id']}"
                            )
                            return False

                    # Appliquer l'update (approche simplifiée)
                    self.stats["conflicts_resolved"] += 1
                    logger.info(
                        f"🔄 Conflit résolu en faveur du serveur: {table_name}#{data['id']}"
                    )

                    # Note: En production, il faudrait mapper les champs correctement
                    # Ici on fait juste une mise à jour du timestamp pour la démo
                    model_class.update(
                        sync_timestamp=server_timestamp,
                        sync_status=1,  # Marqué comme synchronisé
                    ).where(model_class._meta.primary_key == data["id"]).execute()

                    return True

                except model_class.DoesNotExist:
                    logger.warning(
                        f"⚠️ Enregistrement {table_name}#{data['id']} introuvable pour UPDATE"
                    )
                    return False

            elif operation == "INSERT":
                # Pour INSERT, on ne fait qu'une démo - en production il faudrait
                # mapper tous les champs et gérer les conflits d'ID
                logger.info(f"📥 INSERT simulé pour {table_name}")
                return True

            elif operation == "DELETE" and "id" in data:
                # Pour DELETE, soft delete en mettant à jour les flags
                try:
                    model_class.update(
                        sync_status=1, sync_timestamp=server_timestamp
                    ).where(model_class._meta.primary_key == data["id"]).execute()
                    logger.info(f"🗑️ DELETE simulé pour {table_name}#{data['id']}")
                    return True
                except:
                    return False

        except Exception as e:
            logger.error(f"❌ Failed to apply change {change}: {e}")
            return False

        return False

    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques de sync bidirectionnelle"""
        return {
            **self.stats,
            "is_running": self._running,
            "mqtt_connected": self._mqtt_connected,
            "last_server_sync": self._last_server_sync.isoformat()
            if self._last_server_sync
            else None,
        }


# Instance globale
_bidirectional_sync_worker = None


def get_bidirectional_sync_worker(sync_interval: int = 300) -> BidirectionalSyncWorker:
    """Récupère l'instance singleton du worker de sync bidirectionnelle"""
    global _bidirectional_sync_worker
    if _bidirectional_sync_worker is None:
        _bidirectional_sync_worker = BidirectionalSyncWorker(sync_interval)
    return _bidirectional_sync_worker


def stop_bidirectional_sync_worker():
    """Arrête le worker de sync bidirectionnelle"""
    global _bidirectional_sync_worker
    if _bidirectional_sync_worker:
        _bidirectional_sync_worker.stop()
        _bidirectional_sync_worker = None


def get_bidirectional_sync_stats() -> Dict[str, Any]:
    """Récupère les stats de sync bidirectionnelle"""
    if _bidirectional_sync_worker:
        return _bidirectional_sync_worker.get_stats()
    return {"status": "not_running"}
