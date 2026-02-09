#!/usr/bin/env python3
"""
🧪 Test du système complet de surveillance
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.business.running_processes import scan_running_processes
from core.business.db import get_running_instances
from core.component.logger import get_logger

logger = get_logger("test_system")


def test_complete_system():
    """Test du système complet avec les corrections d'encodage"""

    print("🚀 Test du système complet de surveillance")
    print("=" * 50)

    # 1. Scanner les processus actuels
    print("\n1. 🔍 Scan des processus en cours...")
    try:
        scan_running_processes()
        print("   ✅ Scan terminé avec succès")
    except Exception as e:
        print(f"   ❌ Erreur lors du scan: {e}")
        return

    # 2. Récupérer quelques instances
    print("\n2. 📋 Récupération des instances...")
    try:
        instances = get_running_instances()
        if instances:
            print(f"   ✅ {len(instances)} instances trouvées")

            # Afficher quelques exemples
            for i, instance in enumerate(instances[:5]):
                print(
                    f"   📊 {i + 1}. PID {instance.pri_pid}: {instance.process.prc_name}"
                )
                if hasattr(instance, "signed_by") and instance.signed_by:
                    # Limite l'affichage du subject à 60 caractères
                    subject = (
                        instance.signed_by[:60] + "..."
                        if len(instance.signed_by) > 60
                        else instance.signed_by
                    )
                    print(f"        🔐 Signé par: {subject}")
                print(f"        📂 Chemin: {instance.process.prc_path[:80]}...")
        else:
            print("   ⚠️ Aucune instance trouvée")
    except Exception as e:
        print(f"   ❌ Erreur lors de la récupération: {e}")

    print("\n🎯 Test terminé!")


if __name__ == "__main__":
    test_complete_system()
