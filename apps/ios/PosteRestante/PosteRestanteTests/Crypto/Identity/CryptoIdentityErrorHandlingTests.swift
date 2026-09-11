//
//  CryptoIdentityErrorHandlingTests.swift
//  PosteRestante
//
//  Created by Muhammad Akbar Reishandy on 11/09/26.
//

import XCTest
@testable import PosteRestante

final class CryptoIdentityErrorHandlingTests: XCTestCase {
	private let testService = "id.reishandy.PosteRestante.tests.errors"
	private var sut: CryptoIdentityManager!
	
	override func setUp() async throws {
		try await super.setUp()
		sut = CryptoIdentityManager(service: testService, account: "error-test-\(UUID().uuidString)")
	}
	
	override func tearDown() async throws {
		try? await sut.deleteIdentityKey()
		sut = nil
		try await super.tearDown()
	}
	
	func test_deriveSharedMasterSecret_throwsOnSelfHandshake() async throws {
		let myPublicKey = try await sut.exportPublicKeyBytes()
		
		do {
			_ = try await sut.deriveSharedMasterSecret(peerPublicKeyBytes: myPublicKey)
			XCTFail("Expected selfHandshakeNotPermitted error to be thrown")
		} catch let error as CryptoIdentityError {
			XCTAssertEqual(error, .selfHandshakeNotPermitted)
		}
	}
	
	func test_deriveSharedMasterSecret_throwsOnInvalidKeySizes() async {
		let invalidSizes = [0, 16, 31, 33, 64]
		
		for size in invalidSizes {
			let malformedData = Data(repeating: 0xAA, count: size)
			do {
				_ = try await sut.deriveSharedMasterSecret(peerPublicKeyBytes: malformedData)
				XCTFail("Expected invalidKeySize error for size \(size)")
			} catch let error as CryptoIdentityError {
				XCTAssertEqual(error, .invalidKeySize(expected: 32, actual: size))
			} catch {
				XCTFail("Unexpected error type: \(error)")
			}
		}
	}
	
	func test_deleteIdentityKey_succeedsWhenItemDoesNotExist() async {
		// Deleting when nothing has been inserted yet should return gracefully
		do {
			try await sut.deleteIdentityKey()
		} catch {
			XCTFail("Expected deletion of non-existent item to succeed, got: \(error)")
		}
	}
}
