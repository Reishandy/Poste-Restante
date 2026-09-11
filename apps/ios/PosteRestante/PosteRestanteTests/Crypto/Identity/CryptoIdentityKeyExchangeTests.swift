//
//  CryptoIdentityKeyExchangeTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
import CryptoKit
@testable import PosteRestante

final class CryptoIdentityKeyExchangeTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.exchange"
	private var alice: CryptoIdentityManager!
	private var bob: CryptoIdentityManager!
	private var charlie: CryptoIdentityManager!
	
	override func setUp() async throws {
		try await super.setUp()
		alice = CryptoIdentityManager(service: testService, account: "alice-\(UUID().uuidString)")
		bob = CryptoIdentityManager(service: testService, account: "bob-\(UUID().uuidString)")
		charlie = CryptoIdentityManager(service: testService, account: "charlie-\(UUID().uuidString)")
	}
	
	override func tearDown() async throws {
		try? await alice.deleteIdentityKey()
		try? await bob.deleteIdentityKey()
		try? await charlie.deleteIdentityKey()
		alice = nil
		bob = nil
		charlie = nil
		try await super.tearDown()
	}
	
	func test_deriveSharedMasterSecret_aliceAndBobDeriveIdenticalSecret() async throws {
		let alicePublic = try await alice.exportPublicKeyBytes()
		let bobPublic = try await bob.exportPublicKeyBytes()
		
		let aliceSharedKey = try await alice.deriveSharedMasterSecret(peerPublicKeyBytes: bobPublic)
		let bobSharedKey = try await bob.deriveSharedMasterSecret(peerPublicKeyBytes: alicePublic)
		
		let aliceKeyData = aliceSharedKey.withUnsafeBytes { Data($0) }
		let bobKeyData = bobSharedKey.withUnsafeBytes { Data($0) }
		
		XCTAssertEqual(aliceKeyData, bobKeyData)
		XCTAssertEqual(aliceKeyData.count, 32)
	}
	
	func test_deriveSharedMasterSecret_producesDifferentKeysForDifferentPeers() async throws {
		let bobPublic = try await bob.exportPublicKeyBytes()
		let charliePublic = try await charlie.exportPublicKeyBytes()
		
		let secretWithBob = try await alice.deriveSharedMasterSecret(peerPublicKeyBytes: bobPublic)
		let secretWithCharlie = try await alice.deriveSharedMasterSecret(peerPublicKeyBytes: charliePublic)
		
		let bobSecretData = secretWithBob.withUnsafeBytes { Data($0) }
		let charlieSecretData = secretWithCharlie.withUnsafeBytes { Data($0) }
		
		XCTAssertNotEqual(bobSecretData, charlieSecretData)
	}
}
