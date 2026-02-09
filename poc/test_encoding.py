#!/usr/bin/env python3
"""
🧪 Script de test pour les problèmes d'encodage PowerShell
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.business.process import (
    get_file_signer_simple,
    get_file_signer_with_timeout,
    get_file_signer,
)


def test_encoding_fixes():
    """Test les différentes fonctions de signature"""

    # Fichiers Windows système connus pour avoir des signatures
    test_files = [
        r"C:\Windows\System32\notepad.exe",
        r"C:\Windows\explorer.exe",
        r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
        if os.path.exists(
            r"C:\Program Files\Microsoft Office\root\Office16\WINWORD.EXE"
        )
        else None,
    ]

    # Filtrer les fichiers qui existent
    test_files = [f for f in test_files if f and os.path.exists(f)]

    if not test_files:
        print("❌ Aucun fichier de test trouvé")
        return

    for file_path in test_files[:1]:  # Test seulement le premier fichier
        print(f"\n🧪 Test de: {file_path}")

        # Test version originale
        print("\n1. Version originale (get_file_signer):")
        try:
            result_orig = get_file_signer(file_path)
            if result_orig:
                print(f"   ✅ Subject: {result_orig.get('subject', 'N/A')}")
                print(f"   📋 Thumbprint: {result_orig.get('thumbprint', 'N/A')}")
                print(f"   🔒 EV Certificate: {result_orig.get('is_ev', False)}")
            else:
                print("   ❌ Pas de signature détectée")
        except Exception as e:
            print(f"   💥 Erreur: {e}")

        # Test version simple
        print("\n2. Version simple (get_file_signer_simple):")
        try:
            result_simple = get_file_signer_simple(file_path)
            if result_simple:
                print(f"   ✅ Subject: {result_simple.get('subject', 'N/A')}")
                print(f"   📋 Thumbprint: {result_simple.get('thumbprint', 'N/A')}")
                print(f"   🔒 EV Certificate: {result_simple.get('is_ev', False)}")
            else:
                print("   ❌ Pas de signature détectée")
        except Exception as e:
            print(f"   💥 Erreur: {e}")

        # Test version avec timeout
        print("\n3. Version avec timeout (get_file_signer_with_timeout):")
        try:
            result_timeout = get_file_signer_with_timeout(file_path, timeout=10)
            if result_timeout:
                print(f"   ✅ Subject: {result_timeout.get('subject', 'N/A')}")
                print(f"   📋 Thumbprint: {result_timeout.get('thumbprint', 'N/A')}")
                print(f"   🔒 EV Certificate: {result_timeout.get('is_ev', False)}")
            else:
                print("   ❌ Pas de signature détectée")
        except Exception as e:
            print(f"   💥 Erreur: {e}")


if __name__ == "__main__":
    print("🔧 Test des corrections d'encodage PowerShell")
    print("=" * 50)
    test_encoding_fixes()
    print("\n🎯 Test terminé!")
